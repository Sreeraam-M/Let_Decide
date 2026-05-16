import fastf1
import pandas as pd
import os

TYRE_DEG_PER_LAP = 0.5      
FRESH_TYRE_GAIN  = 1.0      
FRESH_TYRE_LAPS  = 12       
FALLBACK_PIT_LOSS = 20.0

def load_session(year: int, gp: str, session_type: str):
    cache_dir = "./fastf1_cache"
    os.makedirs(cache_dir, exist_ok=True)
    fastf1.Cache.enable_cache(cache_dir)
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=False, weather=False, messages=False)
    return session

def get_driver_laps(session, driver: str) -> pd.DataFrame:
    laps = session.laps.pick_driver(driver).copy()
    laps = laps[laps["LapTime"].notna()].copy()
    laps["LapTimeSec"] = laps["LapTime"].dt.total_seconds()
    median_time = laps["LapTimeSec"].median()
    laps = laps[laps["LapTimeSec"] < median_time * 1.15].copy()
    laps = laps[["LapNumber", "LapTimeSec"]].reset_index(drop=True)
    return laps

def get_dynamic_pit_loss(session, driver: str) -> float:
    try:
        laps = session.laps.pick_driver(driver)
        in_laps = laps[laps['PitInTime'].notnull()]
        if not in_laps.empty:
            in_lap = in_laps.iloc[0]
            out_lap = laps[laps['LapNumber'] == in_lap['LapNumber'] + 1]
            if not out_lap.empty:
                diff = out_lap.iloc[0]['PitOutTime'] - in_lap['PitInTime']
                if pd.notnull(diff):
                    return diff.total_seconds()
        
        all_laps = session.laps
        in_laps = all_laps[all_laps['PitInTime'].notnull()]
        total_loss = 0.0
        count = 0
        for _, in_lap in in_laps.iterrows():
            out_lap = all_laps[(all_laps['DriverNumber'] == in_lap['DriverNumber']) & (all_laps['LapNumber'] == in_lap['LapNumber'] + 1)]
            if not out_lap.empty:
                diff = out_lap.iloc[0]['PitOutTime'] - in_lap['PitInTime']
                if pd.notnull(diff):
                    total_loss += diff.total_seconds()
                    count += 1
        if count > 0:
            return total_loss / count
    except Exception:
        pass
    return FALLBACK_PIT_LOSS

def simulate_no_pit(laps_df: pd.DataFrame, from_lap: int) -> float:
    remaining = laps_df[laps_df["LapNumber"] >= from_lap].copy()
    total_time = 0.0
    for i, row in enumerate(remaining.itertuples(index=False)):
        degradation = TYRE_DEG_PER_LAP * i
        total_time += row.LapTimeSec + degradation
    return total_time

def simulate_pit_at(laps_df: pd.DataFrame, from_lap: int, pit_lap: int, pit_time_loss: float) -> float:
    remaining = laps_df[laps_df["LapNumber"] >= from_lap].copy()
    total_time   = 0.0
    laps_on_new  = 0       
    for i, row in enumerate(remaining.itertuples(index=False)):
        lap_n = int(row.LapNumber)
        lap_t = row.LapTimeSec
        if lap_n < pit_lap:
            degradation = TYRE_DEG_PER_LAP * i
            total_time += lap_t + degradation
        elif lap_n == pit_lap:
            degradation = TYRE_DEG_PER_LAP * i   
            total_time += lap_t + degradation + pit_time_loss
            laps_on_new = 0
        else:
            laps_on_new += 1
            fresh_benefit = FRESH_TYRE_GAIN if laps_on_new <= FRESH_TYRE_LAPS else 0.0
            new_deg       = TYRE_DEG_PER_LAP * laps_on_new
            total_time   += lap_t - fresh_benefit + new_deg
    return total_time

def compare_strategies_api(year: int, gp: str, session_type: str, driver: str, decision_lap: int, strategy: str):
    try:
        session = load_session(year, gp, session_type)
        laps_df = get_driver_laps(session, driver)
        
        if laps_df.empty:
            return {
                "unregistered_data": True,
                "title": "No Telemetry Data",
                "message": f"No valid lap data found for driver '{driver}'. They may have DNS or the race data is corrupted."
            }
            
        max_lap = int(laps_df["LapNumber"].max())
        min_lap = int(laps_df["LapNumber"].min())
        
        # Get winner data
        try:
            winner_row = session.results.iloc[0]
            winner_name = str(winner_row['Abbreviation'])
            winner_time_td = winner_row['Time']
            winner_time_sec = winner_time_td.total_seconds() if pd.notnull(winner_time_td) else None
        except Exception:
            winner_name = "UNK"
            winner_time_sec = None

        winner_laps_df = get_driver_laps(session, winner_name)
        winner_max_lap = int(winner_laps_df["LapNumber"].max()) if not winner_laps_df.empty else max_lap
        
        # DNF / Red Flag Check
        if max_lap < winner_max_lap * 0.9:
            return {
                "unregistered_data": True,
                "title": "Incomplete Race (DNF)",
                "message": f"{driver} completed only {max_lap} clean laps compared to the winner's {winner_max_lap}. Full race strategy cannot be simulated."
            }

        if decision_lap < min_lap or decision_lap >= max_lap:
            return {
                "unregistered_data": True,
                "title": "Invalid Decision Lap",
                "message": f"Lap {decision_lap} is out of range. Valid clean laps for {driver}: {min_lap} - {max_lap - 1}"
            }
            
        # Get dynamic pit loss
        pit_time_loss = get_dynamic_pit_loss(session, driver)
        winner_pit_time_loss = get_dynamic_pit_loss(session, winner_name) if winner_name != "UNK" else None
        
        pit_now_lap   = decision_lap
        pit_later_lap = min(decision_lap + 3, max_lap)

        time_pit_now   = simulate_pit_at(laps_df, decision_lap, pit_now_lap, pit_time_loss)
        time_pit_later = simulate_pit_at(laps_df, decision_lap, pit_later_lap, pit_time_loss)

        chosen_lap = pit_now_lap if strategy == "pit now" else pit_later_lap
        chosen_time = time_pit_now if strategy == "pit now" else time_pit_later
        other_time  = time_pit_later if strategy == "pit now" else time_pit_now
        other_label = f"pit after 3 laps" if strategy == "pit now" else f"pit now"

        laps_after_pit = max_lap - chosen_lap
        actual_benefit_laps = min(laps_after_pit, FRESH_TYRE_LAPS)
        fresh_tyre_gain     = actual_benefit_laps * FRESH_TYRE_GAIN
        net_benefit_vs_no_pit = pit_time_loss - fresh_tyre_gain

        net_vs_alternative  = chosen_time - other_time
        verdict = "Good Strategy" if net_vs_alternative <= 0 else "Bad Strategy"
        
        # Calculate full simulated race time
        past_laps = laps_df[laps_df["LapNumber"] < decision_lap]
        time_before_decision = past_laps["LapTimeSec"].sum()
        simulated_total_race_time = time_before_decision + chosen_time
        
        # Calculate actual cumulative clean time
        actual_total_race_time = laps_df["LapTimeSec"].sum()
        
        # Graph Data Generation
        def get_clean_cumulative_trace(df):
            trace = {}
            cum_time = 0
            for row in df.itertuples():
                cum_time += row.LapTimeSec
                trace[row.LapNumber] = cum_time
            return trace

        winner_trace = get_clean_cumulative_trace(winner_laps_df)
        actual_trace = get_clean_cumulative_trace(laps_df)
        
        # Build simulated trace
        sim_trace = {}
        cum_time = 0
        for row in past_laps.itertuples():
            cum_time += row.LapTimeSec
            sim_trace[row.LapNumber] = cum_time
            
        remaining = laps_df[laps_df["LapNumber"] >= decision_lap]
        laps_on_new = 0
        for i, row in enumerate(remaining.itertuples(index=False)):
            lap_n = int(row.LapNumber)
            lap_t = row.LapTimeSec
            if lap_n < chosen_lap:
                sim_lap_t = lap_t + (TYRE_DEG_PER_LAP * i)
            elif lap_n == chosen_lap:
                sim_lap_t = lap_t + (TYRE_DEG_PER_LAP * i) + pit_time_loss
                laps_on_new = 0
            else:
                laps_on_new += 1
                sim_lap_t = lap_t - (FRESH_TYRE_GAIN if laps_on_new <= FRESH_TYRE_LAPS else 0.0) + (TYRE_DEG_PER_LAP * laps_on_new)
            cum_time += sim_lap_t
            sim_trace[lap_n] = cum_time

        all_laps = sorted(list(set(list(winner_trace.keys()) + list(actual_trace.keys()) + list(sim_trace.keys()))))
        graph_data = []
        for lap in all_laps:
            graph_data.append({
                "lap": lap,
                "winner_time": round(winner_trace.get(lap), 2) if lap in winner_trace else None,
                "actual_time": round(actual_trace.get(lap), 2) if lap in actual_trace else None,
                "simulated_time": round(sim_trace.get(lap), 2) if lap in sim_trace else None
            })

        # Calculate robust clean air delta to winner
        delta_to_winner = None
        if winner_max_lap in winner_trace:
            delta_to_winner = simulated_total_race_time - winner_trace[winner_max_lap]

        return {
            "success": True,
            "driver": driver,
            "decision_lap": decision_lap,
            "chosen_strategy": strategy,
            "chosen_lap": chosen_lap,
            "pit_time_loss": pit_time_loss,
            "winner_pit_time_loss": winner_pit_time_loss,
            "benefit_laps": actual_benefit_laps,
            "time_gained_new_tyres": fresh_tyre_gain,
            "net_vs_no_pit": net_benefit_vs_no_pit,
            "total_time_chosen": chosen_time,
            "total_time_other": other_time,
            "other_label": other_label,
            "net_difference": net_vs_alternative,
            "verdict": verdict,
            "min_lap": min_lap,
            "max_lap": max_lap,
            "winner_name": winner_name,
            "winner_time": round(winner_trace.get(winner_max_lap, 0), 2) if winner_max_lap in winner_trace else None,
            "actual_total_race_time": actual_total_race_time,
            "simulated_total_race_time": simulated_total_race_time,
            "delta_to_winner": delta_to_winner,
            "graph_data": graph_data
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
