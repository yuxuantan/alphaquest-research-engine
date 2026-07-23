# full_session_signed_two_sided_impulse_pause_breakout_1530

From 09:45:00 through 15:30:00 ET, wait for 3 completed 5-minute bars to move at least the declared impulse threshold, then require 3 completed pause bars whose retrace is no more than 55% of that impulse. A trade is signaled only when the next completed bar closes beyond the pause boundary with same-direction signed_volume imbalance; direction is long and short.

Mechanics review: This variant expresses impulse-pause continuation by using a full-session opportunity set but still requiring three completed phases: directional impulse, shallow pause, and breakout close. From 09:45:00 through 15:30:00 ET, wait for 3 completed 5-minute bars to move at least the declared impulse threshold, then require 3 completed pause bars whose retrace is no more than 55% of that impulse. A trade is signaled only when the next completed bar closes beyond the pause boundary with same-direction signed_volume imbalance; direction is long and short. The variant should be profitable only if impulse-pause-breakout continuation is a broad completed-bar behavior rather than a narrow morning-only artifact, with aggregate flow showing that breakout pressure is still active after the pause.

Signal timing: all impulse, pause, breakout, and orderflow inputs are completed before the signal is emitted; entry can occur no earlier than the next 5-minute bar open.

Parameter grid: `entry.params.min_impulse_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations. `target_r_multiple` starts at 1.0R; sub-1R targets are not allowed. No PnL was inspected before this grid was written.

## Rescue parameter-space attempt 1

Original best run used the widest declared stop while the full-session formulation remained dense. The rescue expands only stop distance to test whether broad-session continuation is being cut off too quickly.

Scope: entry/stop parameter values only as listed in `config.yaml`; entry, stop, and target modules are unchanged. The target grid remains `[1.0, 1.5, 2.0]`; no sub-1R target is allowed.
