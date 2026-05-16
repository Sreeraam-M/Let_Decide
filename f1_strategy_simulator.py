"""
F1 Team Principal Strategy Simulator
=====================================
Evaluates pit stop decisions for a single driver in a single race
using FastF1 for real lap time data and Pandas for data handling.

Usage:
    pip install fastf1 pandas
    python f1_strategy_simulator.py
"""

import fastf1
import pandas as pd
import os

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
YEAR        = 2023
GRAND_PRIX  = "Bahrain"
SESSION     = "R"           # R = Race
DRIVER      = "VER"         # Verstappen (change to any 3-letter code)

PIT_TIME_LOSS   = 20.0      # seconds lost in the pit lane
TYRE_DEG_PER_LAP = 0.5      # seconds added per lap on worn tyres
FRESH_TYRE_GAIN  = 1.0      # seconds saved per lap on fresh rubber
FRESH_TYRE_LAPS  = 12       # how many laps the fresh-tyre benefit lasts


# ─────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────

def load_session(year: int, gp: str, session_type: str):
    """Load and return a FastF1 session, with a local cache."""
    cache_dir = "./fastf1_cache"
    os.makedirs(cache_dir, exist_ok=True)
    fastf1.Cache.enable_cache(cache_dir)

    print(f"\n📡  Loading {year} {gp} GP – session '{session_type}' …")
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=False, weather=False, messages=False)
    print("✅  Session loaded.\n")
    return session


def get_driver_laps(session, driver: str) -> pd.DataFrame:
    """Return a clean DataFrame of valid lap times for one driver."""
    laps = session.laps.pick_driver(driver).copy()

    # Keep only classified (green-flag) laps with a recorded time
    laps = laps[laps["LapTime"].notna()].copy()
    laps["LapTimeSec"] = laps["LapTime"].dt.total_seconds()

    # Drop obvious outliers (pit-in/out laps, safety-car laps, etc.)
    median_time = laps["LapTimeSec"].median()
    laps = laps[laps["LapTimeSec"] < median_time * 1.15].copy()

    laps = laps[["LapNumber", "LapTimeSec"]].reset_index(drop=True)
    return laps


# ─────────────────────────────────────────────
# SIMULATION LOGIC
# ─────────────────────────────────────────────

def simulate_no_pit(laps_df: pd.DataFrame, from_lap: int) -> float:
    """
    Baseline: driver stays out with no pit stop.
    Tyre degradation accumulates 0.5 s/lap for every lap after `from_lap`.
    Returns total race time from `from_lap` to end of race.
    """
    remaining = laps_df[laps_df["LapNumber"] >= from_lap].copy()

    total_time = 0.0
    for i, row in enumerate(remaining.itertuples(index=False)):
        # Each lap the tyres are a little slower
        degradation = TYRE_DEG_PER_LAP * i
        total_time += row.LapTimeSec + degradation

    return total_time


def simulate_pit_at(laps_df: pd.DataFrame, from_lap: int, pit_lap: int) -> float:
    """
    Simulate pitting at `pit_lap`.
    - Pit lap itself costs PIT_TIME_LOSS extra seconds.
    - For FRESH_TYRE_LAPS after the pit, each lap is FRESH_TYRE_GAIN faster.
    - Tyre degradation clock resets to zero after the pit.
    Returns total race time from `from_lap` to end of race.
    """
    remaining = laps_df[laps_df["LapNumber"] >= from_lap].copy()

    total_time   = 0.0
    laps_on_new  = 0       # counter for fresh-tyre benefit

    for i, row in enumerate(remaining.itertuples(index=False)):
        lap_n = int(row.LapNumber)
        lap_t = row.LapTimeSec

        if lap_n < pit_lap:
            # Still on old rubber – add degradation from `from_lap`
            degradation = TYRE_DEG_PER_LAP * i
            total_time += lap_t + degradation

        elif lap_n == pit_lap:
            # Pit stop lap: lose pit-lane time, tyre deg resets
            degradation = TYRE_DEG_PER_LAP * i   # deg up to this point
            total_time += lap_t + degradation + PIT_TIME_LOSS
            laps_on_new = 0

        else:
            # Post-pit: fresh tyres, new deg counter
            laps_on_new += 1
            fresh_benefit = FRESH_TYRE_GAIN if laps_on_new <= FRESH_TYRE_LAPS else 0.0
            new_deg       = TYRE_DEG_PER_LAP * laps_on_new
            total_time   += lap_t - fresh_benefit + new_deg

    return total_time


# ─────────────────────────────────────────────
# COMPARISON & VERDICT
# ─────────────────────────────────────────────

def compare_strategies(laps_df: pd.DataFrame, decision_lap: int, strategy: str):
    """
    Compare 'pit now' vs 'pit after 3 laps' from the driver's perspective
    at `decision_lap`, then explain the chosen strategy vs the alternative.
    """
    max_lap = int(laps_df["LapNumber"].max())

    # Validate lap range
    if decision_lap < int(laps_df["LapNumber"].min()) or decision_lap >= max_lap:
        raise ValueError(
            f"Lap {decision_lap} is out of range. "
            f"Valid range: {int(laps_df['LapNumber'].min())} – {max_lap - 1}"
        )

    pit_now_lap   = decision_lap
    pit_later_lap = min(decision_lap + 3, max_lap)

    time_pit_now   = simulate_pit_at(laps_df, decision_lap, pit_now_lap)
    time_pit_later = simulate_pit_at(laps_df, decision_lap, pit_later_lap)

    chosen_lap = pit_now_lap if strategy == "pit now" else pit_later_lap
    chosen_time = time_pit_now if strategy == "pit now" else time_pit_later
    other_time  = time_pit_later if strategy == "pit now" else time_pit_now
    other_label = f"pit after 3 laps (lap {pit_later_lap})" \
                  if strategy == "pit now" else f"pit now (lap {pit_now_lap})"

    # Benefit breakdown for the chosen strategy
    baseline_time = simulate_no_pit(laps_df, decision_lap)
    time_vs_no_pit = chosen_time - baseline_time

    laps_after_pit = max_lap - chosen_lap
    actual_benefit_laps = min(laps_after_pit, FRESH_TYRE_LAPS)
    fresh_tyre_gain     = actual_benefit_laps * FRESH_TYRE_GAIN
    net_benefit_vs_no_pit = PIT_TIME_LOSS - fresh_tyre_gain

    net_vs_alternative  = chosen_time - other_time

    # Verdict: chosen strategy is GOOD if it's faster than the alternative
    verdict = "✅  Good Strategy" if net_vs_alternative <= 0 else "❌  Bad Strategy"

    # ── Print report ──────────────────────────────────────────────
    print("=" * 54)
    print("   🏎️   F1 TEAM PRINCIPAL STRATEGY SIMULATOR")
    print("=" * 54)
    print(f"  Race   : {YEAR} {GRAND_PRIX} GP")
    print(f"  Driver : {DRIVER}")
    print(f"  Decision at lap : {decision_lap}")
    print(f"  Chosen strategy : {strategy.upper()} (lap {chosen_lap})")
    print("-" * 54)
    print(f"  Time lost in pit stop      : +{PIT_TIME_LOSS:.1f} s")
    print(f"  Fresh-tyre benefit laps    :  {actual_benefit_laps} laps")
    print(f"  Time gained from new tyres : -{fresh_tyre_gain:.1f} s")
    print(f"  Net vs. staying out        : {'+' if net_benefit_vs_no_pit >= 0 else ''}"
          f"{net_benefit_vs_no_pit:.1f} s")
    print("-" * 54)
    print(f"  Total time (chosen)        : {chosen_time:.2f} s")
    print(f"  Total time ({other_label[:18]:<18}) : {other_time:.2f} s")
    print(f"  Net difference             : "
          f"{'+' if net_vs_alternative >= 0 else ''}{net_vs_alternative:.2f} s  "
          f"({'worse' if net_vs_alternative > 0 else 'better'} than the alternative)")
    print("=" * 54)
    print(f"  VERDICT : {verdict}")
    print("=" * 54)


# ─────────────────────────────────────────────
# USER INPUT
# ─────────────────────────────────────────────

def get_user_inputs(min_lap: int, max_lap: int) -> tuple[int, str]:
    """Prompt the user for a lap number and a strategy choice."""
    print(f"\nAvailable laps for {DRIVER}: {min_lap} – {max_lap - 1}")

    while True:
        try:
            lap = int(input("Enter the lap number where you want to decide: "))
            if min_lap <= lap < max_lap:
                break
            print(f"  ⚠️  Please enter a lap between {min_lap} and {max_lap - 1}.")
        except ValueError:
            print("  ⚠️  Please enter a valid integer.")

    print("\nStrategy options:")
    print("  1. pit now      – pit on this lap")
    print("  2. pit after 3 laps – stay out 3 more laps, then pit")

    while True:
        choice = input("Your choice (1 or 2): ").strip()
        if choice == "1":
            return lap, "pit now"
        elif choice == "2":
            return lap, "pit after 3 laps"
        print("  ⚠️  Enter 1 or 2.")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    # 1. Load race session
    session = load_session(YEAR, GRAND_PRIX, SESSION)

    # 2. Extract driver lap times
    laps_df = get_driver_laps(session, DRIVER)
    if laps_df.empty:
        print(f"❌  No valid lap data found for driver '{DRIVER}'.")
        return

    min_lap = int(laps_df["LapNumber"].min())
    max_lap = int(laps_df["LapNumber"].max())

    print(f"Loaded {len(laps_df)} clean laps for {DRIVER}  "
          f"(laps {min_lap}–{max_lap})")
    print(f"Median lap time : {laps_df['LapTimeSec'].median():.3f} s  "
          f"({laps_df['LapTimeSec'].median()/60:.2f} min)")

    # 3. Get user input
    decision_lap, strategy = get_user_inputs(min_lap, max_lap)

    # 4 & 5. Simulate and compare both strategies
    compare_strategies(laps_df, decision_lap, strategy)


if __name__ == "__main__":
    main()
