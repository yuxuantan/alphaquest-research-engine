# late_morning_signed_short_ema_pullback_1200

This variant tests short-only late-morning EMA pullback continuation using signed-volume sell pressure.

- Entry module: `ema_pullback_orderflow_continuation`
- Stop module: `sweep_extreme`
- Target module: `fixed_r`
- Timeframe: 5-minute ES RTH bars from the local Sierra aggregate-orderflow cache
- Entry window: 10:30:00 to 12:00:00 ET
- Forced strategy flatten: 14:00:00 ET

The variant uses only completed bars. The EMA trend state is based on prior completed closes before the signal bar close is incorporated, and any signal is entered no earlier than the next 5-minute bar open by the backtest engine.
