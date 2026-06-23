# midday_signed_gap_hold_continuation_1200

Campaign: `nq_opening_gap_orderflow_continuation`

Entry module: `opening_gap_orderflow_continuation`. Stop module: `opening_gap_boundary`. Target module: `fixed_r`.

Mechanic: accepted NQ opening-gap continuation through the completed 11:45:00 to 12:00:00 ET source window using signed-volume confirmation.

Parameter grid: `entry.params.min_opening_gap_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.max_stop_points` x `tp.params.target_r_multiple` = 81 combinations.

Pre-PnL density note: midday signed broad/mid corners 58-78 signals/year; strict g60/i0.02 about 44/year before stop cap.
