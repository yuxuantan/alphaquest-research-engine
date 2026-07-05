# afternoon_large10_two_sided_ema_pullback_1430

This variant tests two-sided afternoon EMA pullback continuation confirmed by 10-lot-or-larger aggregate flow.

- Entry module: `ema_pullback_orderflow_continuation`
- Stop module: `sweep_extreme`
- Target module: `fixed_r`
- Timeframe: 5-minute NQ RTH bars from the local Sierra aggregate-orderflow cache
- Entry window: 12:30:00 to 14:30:00 ET
- Forced strategy flatten: 15:30:00 ET

The variant uses only completed bars. The EMA trend state is based on prior completed closes before the signal bar close is incorporated, and any signal is entered no earlier than the next 5-minute bar open by the backtest engine.
