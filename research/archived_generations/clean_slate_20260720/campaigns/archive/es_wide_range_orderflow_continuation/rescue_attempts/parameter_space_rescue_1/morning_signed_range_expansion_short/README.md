# morning_signed_range_expansion_short rescue1

Parameter-space-only rescue for `es_wide_range_orderflow_continuation`. The entry module, stop module, target module, data window, costs, sessions, fill rules, and core mechanic are unchanged.

Changed grid: `min_range_ticks: [10, 12]`, `min_orderflow_imbalance: [0.0, 0.02, 0.04]`, `stop_pct: [0.004, 0.005, 0.006]`, `target_r_multiple: [1.0, 1.5, 2.0]`.
