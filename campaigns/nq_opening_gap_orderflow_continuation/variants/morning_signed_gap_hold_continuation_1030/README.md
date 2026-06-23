# morning_signed_gap_hold_continuation_1030

Campaign: `nq_opening_gap_orderflow_continuation`

Entry module: `opening_gap_orderflow_continuation`. Stop module: `opening_gap_boundary`. Target module: `fixed_r`.

Mechanic: accepted NQ opening-gap continuation through the completed 10:15:00 to 10:30:00 ET source window using signed-volume confirmation.

Parameter grid: `entry.params.min_opening_gap_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.max_stop_points` x `tp.params.target_r_multiple` = 81 combinations.

Pre-PnL density note: morning signed broad/mid corners 52-79 signals/year; strict g60/i0.02 about 40/year before stop cap.
