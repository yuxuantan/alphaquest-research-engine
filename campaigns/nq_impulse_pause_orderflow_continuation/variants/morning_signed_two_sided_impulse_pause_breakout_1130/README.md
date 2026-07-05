# morning_signed_two_sided_impulse_pause_breakout_1130

From 09:45:00 through 11:30:00 ET, wait for 3 completed 5-minute bars to move at least the declared impulse threshold, then require 2 completed pause bars whose retrace is no more than 50% of that impulse. A trade is signaled only when the next completed bar closes beyond the pause boundary with same-direction signed_volume imbalance; direction is long and short.

Mechanics review: This variant expresses impulse-pause continuation because it separates the setup into three completed phases: directional impulse, shallow pause, and breakout close. From 09:45:00 through 11:30:00 ET, wait for 3 completed 5-minute bars to move at least the declared impulse threshold, then require 2 completed pause bars whose retrace is no more than 50% of that impulse. A trade is signaled only when the next completed bar closes beyond the pause boundary with same-direction signed_volume imbalance; direction is long and short. The variant should be profitable only if a shallow pause after a real impulse marks absorption of counterflow and the breakout close with aligned aggregate flow captures unfinished order splitting or liquidity-taking pressure after costs.

Signal timing: all impulse, pause, breakout, and orderflow inputs are completed before the signal is emitted; entry can occur no earlier than the next 5-minute bar open.

Parameter grid: `entry.params.min_impulse_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations. `target_r_multiple` starts at 1.0R; sub-1R targets are not allowed. No PnL was inspected before this grid was written.
