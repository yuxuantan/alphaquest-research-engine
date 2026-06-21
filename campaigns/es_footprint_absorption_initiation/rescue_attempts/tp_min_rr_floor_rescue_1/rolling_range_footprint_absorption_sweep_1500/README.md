# rolling_range_footprint_absorption_sweep_1500

This variant tests two-sided footprint absorption at rolling 60-minute intraday extremes.

- Entry module: `footprint_absorption_initiation`
- Stop module: `sweep_extreme`
- Target module: `fixed_r`
- Timeframe: 1-minute ES RTH bars from the local Sierra footprint cache
- Entry window: 10:45:00 to 15:00:00 ET
- Forced strategy flatten: 15:45:00 ET

The variant uses only completed 1-minute bars. Rolling high/low levels are built from prior bars only, and any signal is entered no earlier than the next 1-minute bar open by the backtest engine.

Rescue attempt 1 changes only declared/fixed parameters: confirmation grid `[1, 2, 3]`, target-R grid `[0.75, 1.0, 1.5]`, fixed confirmation `2`, and fixed target `1.0`. Mechanics, modules, data, costs, fills, sessions, and gates are unchanged.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_footprint_absorption_initiation/rolling_range_footprint_absorption_sweep_1500/rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.
