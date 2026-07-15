# afternoon_large20_two_sided_key_reversal_1530

From 13:00 through 15:30 ET, enter in the reversal direction after a completed 1-minute bar sweeps the prior completed 1-minute bar extreme, closes back through the prior close, shows reversal body and close-location confirmation, and has same-direction large20 trade-size imbalance.

Mechanics review: this is a one-minute prior-bar key-reversal setup, not a fixed-level or rolling-range setup. The immediately prior completed one-minute bar supplies the known high, low, and close. The signal bar must sweep one side, close back through the prior close, show reversal body/close-location confirmation, and align with completed Sierra aggregate flow. Entry can occur no earlier than the next one-minute bar open.

Pre-PnL reformulation note: the first 5-minute version failed the density screen before any PnL was inspected. This 1-minute version keeps the same edge mechanic but uses the timeframe that matches a local micro-breakout/rejection pattern.

Parameter grid: `min_sweep_ticks` x `min_orderflow_imbalance` x `stop_offset_ticks` x `target_r_multiple` = 54 combinations. No PnL was inspected before this grid was written.

## Rescue attempt 1

Run1 had zero profitable limited-core combinations. This rescue keeps the same prior-bar key-reversal entry, `sweep_extreme` stop, and `fixed_r` target, but raises fixed signal-quality thresholds and shifts the stop/target grid wider. It does not invert direction, add a new filter, or change the data/cost/session assumptions.
