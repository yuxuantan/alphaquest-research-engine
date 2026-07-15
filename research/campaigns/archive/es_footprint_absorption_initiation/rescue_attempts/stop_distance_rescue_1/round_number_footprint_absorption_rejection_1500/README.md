# round_number_footprint_absorption_rejection_1500

This variant tests two-sided footprint absorption around 25-point ES handles.

- Entry module: `footprint_absorption_initiation`
- Stop module: `sweep_extreme`
- Target module: `fixed_r`
- Timeframe: 1-minute ES RTH bars from the local Sierra footprint cache
- Entry window: 10:00:00 to 15:00:00 ET
- Forced strategy flatten: 15:45:00 ET

The variant uses only completed 1-minute bars. Round-number levels are determined from information available on the completed signal bar, and any signal is entered no earlier than the next 1-minute bar open by the backtest engine.

Rescue attempt 1 changes only declared/fixed parameters: confirmation grid `[1, 2, 3]`, target-R grid `[0.75, 1.0, 1.5]`, fixed confirmation `2`, and fixed target `1.0`. Mechanics, modules, data, costs, fills, sessions, and gates are unchanged.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_footprint_absorption_initiation/round_number_footprint_absorption_rejection_1500/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.
