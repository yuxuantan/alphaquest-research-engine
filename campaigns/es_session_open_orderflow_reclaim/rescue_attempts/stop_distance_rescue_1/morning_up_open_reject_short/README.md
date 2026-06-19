# morning_up_open_reject_short rescue1

Campaign: `es_session_open_orderflow_reclaim`

This is the single allowed rescue for `morning_up_open_reject_short`. It keeps the same `session_open_orderflow_reclaim` entry module, `percent_from_entry` stop module, `fixed_r` target module, timeframe, data, costs, fills, session rules, and staged validation gates.

Changed parameter space only: `entry.params.min_open_extension_ticks = [8, 10, 12]`, `entry.params.min_orderflow_imbalance = [0.30, 0.40, 0.50]`, `sl.params.stop_pct = [0.0025, 0.004, 0.006]`, and `tp.params.target_r_multiple = [1.0, 1.5, 2.0]`.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_session_open_orderflow_reclaim/morning_up_open_reject_short/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.
