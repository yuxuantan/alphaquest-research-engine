# prior_extreme_footprint_absorption_reversal_1500

This variant tests two-sided footprint absorption at prior RTH high/low.

- Entry module: `footprint_absorption_initiation`
- Stop module: `sweep_extreme`
- Target module: `fixed_r`
- Timeframe: 1-minute ES RTH bars from the local Sierra footprint cache
- Entry window: 10:00:00 to 15:00:00 ET
- Forced strategy flatten: 15:45:00 ET

The variant uses only completed 1-minute bars. The bid/ask footprint imbalance and close are known only after the signal bar closes, and any signal is entered no earlier than the next 1-minute bar open by the backtest engine.
