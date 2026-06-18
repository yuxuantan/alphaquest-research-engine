# opening_range_footprint_absorption_retest_1100

This variant tests two-sided footprint absorption at the completed 30-minute opening range boundary.

- Entry module: `footprint_absorption_initiation`
- Stop module: `sweep_extreme`
- Target module: `fixed_r`
- Timeframe: 1-minute ES RTH bars from the local Sierra footprint cache
- Entry window: 10:00:00 to 11:00:00 ET
- Forced strategy flatten: 13:00:00 ET

The variant uses only completed 1-minute bars. The opening range is fixed after the first 30 RTH minutes, and any signal is entered no earlier than the next 1-minute bar open by the backtest engine.

Rescue attempt 1 changes only declared/fixed parameters: confirmation grid `[1, 2, 3]`, target-R grid `[0.75, 1.0, 1.5]`, fixed confirmation `2`, and fixed target `1.0`. Mechanics, modules, data, costs, fills, sessions, and gates are unchanged.
