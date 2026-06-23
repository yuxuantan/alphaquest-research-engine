# late_morning_large10_gap_hold_continuation_1100

Campaign: `nq_opening_gap_orderflow_continuation`

Entry module: `opening_gap_orderflow_continuation`. Stop module: `opening_gap_boundary`. Target module: `fixed_r`.

Mechanic: accepted NQ opening-gap continuation through the completed 10:45:00 to 11:00:00 ET source window using large10 aggregate flow confirmation.

Parameter grid: `entry.params.min_opening_gap_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.max_stop_points` x `tp.params.target_r_multiple` = 81 combinations.

Pre-PnL density note: late-morning large10 broad/mid corners 50-73 signals/year; strict g60/i0.15 about 42/year before stop cap.
