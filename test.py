import f1_strategy_simulator
session = f1_strategy_simulator.load_session(2023, "Bahrain", "R")
laps_df = f1_strategy_simulator.get_driver_laps(session, "VER")
print(f"Loaded {len(laps_df)} laps")
