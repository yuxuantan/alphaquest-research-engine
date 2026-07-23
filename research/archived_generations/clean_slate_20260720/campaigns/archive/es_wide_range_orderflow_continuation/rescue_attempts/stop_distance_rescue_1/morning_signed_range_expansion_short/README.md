# morning_signed_range_expansion_short rescue1

Parameter-space-only rescue for `es_wide_range_orderflow_continuation`. The entry module, stop module, target module, data window, costs, sessions, fill rules, and core mechanic are unchanged.

Changed grid: `min_range_ticks: [10, 12]`, `min_orderflow_imbalance: [0.0, 0.02, 0.04]`, `stop_pct: [0.004, 0.005, 0.006]`, `target_r_multiple: [1.0, 1.5, 2.0]`.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_wide_range_orderflow_continuation/morning_signed_range_expansion_short/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.
