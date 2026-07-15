# late_morning_large10_up_sweep_reject_short_1230

From 10:00 through 12:30 ET, enter short only after a completed 1-minute bar sweeps the prior completed 1-minute bar high, closes back below the prior close, has a negative body, closes in the lower part of its range, and has negative large10 trade-size imbalance.

Mechanics review: this is a one-minute prior-bar key-reversal setup, not a fixed-level or rolling-range setup. The immediately prior completed one-minute bar supplies the known high, low, and close. The signal bar must sweep one side, close back through the prior close, show reversal body/close-location confirmation, and align with completed Sierra aggregate flow. Entry can occur no earlier than the next one-minute bar open.

Pre-PnL reformulation note: the first 5-minute version failed the density screen before any PnL was inspected. This 1-minute version keeps the same edge mechanic but uses the timeframe that matches a local micro-breakout/rejection pattern.

Parameter grid: `min_sweep_ticks` x `min_orderflow_imbalance` x `stop_offset_ticks` x `target_r_multiple` = 54 combinations. No PnL was inspected before this grid was written.

## Rescue attempt 1

Run1 had zero profitable limited-core combinations. This rescue keeps the same prior-bar key-reversal entry, `sweep_extreme` stop, and `fixed_r` target, but raises fixed signal-quality thresholds and shifts the stop/target grid wider. It does not invert direction, add a new filter, or change the data/cost/session assumptions.
