# Campaign Test Summary

Campaign: `es_footprint_absorption_initiation`
Decision: FAIL
Updated at: `2026-06-19T07:36:08`

Corrected cache: `data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.parquet`
Data-fix audit: `research_artifacts/footprint_imbalance_zero_diagonal_bug_audit_20260618.md`

All five original source configs and all five one-time per-variant rescue configs were rerun from source with the current engine. Every run failed `limited_core_grid_test`; no run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

| Variant | Run | Profitable Combos | Benchmark Combos | Top Net | Top PF | Top Trades/Year | Fixed Trade Log Rows |
|---|---:|---:|---:|---:|---:|---:|---:|
| `prior_extreme_footprint_absorption_reversal_1500` | `run1` | 0 / 81 | 0 | -1505.0 | 0.5887978142076503 | 31.062477612285225 | 115 |
| `rolling_range_footprint_absorption_sweep_1500` | `run1` | 0 / 81 | 0 | -3877.5 | 0.3422391857506361 | 99.92269804614243 | 207 |
| `round_number_footprint_absorption_rejection_1500` | `run1` | 1 / 81 | 0 | 372.5 | 1.0747991967871486 | 58.534579970581646 | 120 |
| `opening_range_footprint_absorption_retest_1100` | `run1` | 0 / 81 | 0 | -2796.875 | 0.48657641119779715 | 63.20603039230692 | 166 |
| `session_open_footprint_absorption_reclaim_1500` | `run1` | 0 / 81 | 0 | -2873.125 | 0.4878565062388592 | 71.22676542976733 | 190 |
| `prior_extreme_footprint_absorption_reversal_1500` | `rescue1` | 12 / 81 | 0 | 486.25 | 1.2539164490861618 | 16.86329989539791 | 47 |
| `rolling_range_footprint_absorption_sweep_1500` | `rescue1` | 1 / 81 | 0 | 342.5 | 1.0526315789473684 | 53.92095386899354 | 149 |
| `round_number_footprint_absorption_rejection_1500` | `rescue1` | 4 / 81 | 1 | 1416.25 | 1.2434464976364417 | 58.534579970581646 | 84 |
| `opening_range_footprint_absorption_retest_1100` | `rescue1` | 0 / 81 | 0 | -330.0 | 0.8970358814352574 | 30.60502524259072 | 96 |
| `session_open_footprint_absorption_reclaim_1500` | `rescue1` | 0 / 81 | 0 | -1524.375 | 0.5619612068965517 | 37.90048068739913 | 113 |

Best original: `round_number_footprint_absorption_rejection_1500/run1`.
Best rescue: `round_number_footprint_absorption_rejection_1500/rescue1`.

Final decision: FAIL
