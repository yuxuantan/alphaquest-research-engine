# Campaign Test Summary

Campaign: `es_opening_range_nq_orderflow_breakout`
Decision: FAIL
Updated at: `2026-06-19T08:21:46`

Data: `data/cache/orderflow/es_nq_lead_lag_1m_20110103_20260609_full_rth_ny.parquet`
Original density audit: `research_artifacts/es_opening_range_nq_orderflow_breakout_density_audit_20260619.md`
Rescue density audit: `research_artifacts/es_opening_range_nq_orderflow_breakout_rescue1_density_audit_20260619.md`

All five originals and all five allowed long-only rescues failed `limited_core_grid_test`. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

| Variant | Run | Profitable Combos | Benchmark Combos | Top Net | Top PF | Top Trades/Year | Fixed Trade Log Rows |
|---|---:|---:|---:|---:|---:|---:|---:|
| `or15_nq30_signed_breakout_1130` | `run1` | 0 / 81 | 0 | -4552.5 | 0.8994089377451251 | 213.15896580483738 | 327 |
| `or60_nq60_signed_breakout_1300` | `run1` | 0 / 81 | 0 | -4695.0 | 0.8894774011299436 | 174.78654367154522 | 274 |
| `or30_nq15_signed_breakout_1030` | `run1` | 0 / 81 | 0 | -306.25 | 0.9890556597873671 | 142.98502077221735 | 217 |
| `or30_nq30_signed_breakout_1130` | `run1` | 0 / 81 | 0 | -6694.375 | 0.8463623845315279 | 196.2047625753185 | 303 |
| `or15_nq15_signed_breakout_1030` | `run1` | 0 / 81 | 0 | -7640.625 | 0.822641016713092 | 185.1546345910132 | 295 |
| `or15_nq30_signed_breakout_1130` | `rescue1` | 0 / 81 | 0 | -1395.0 | 0.9442390326771261 | 126.07572977481234 | 194 |
| `or60_nq60_signed_breakout_1300` | `rescue1` | 0 / 81 | 0 | -82.5 | 0.9955254237288136 | 90.79481622692357 | 144 |
| `or30_nq15_signed_breakout_1030` | `rescue1` | 0 / 81 | 0 | -33.75 | 0.9974446337308348 | 66.94298699790177 | 111 |
| `or30_nq30_signed_breakout_1130` | `rescue1` | 0 / 81 | 0 | -3211.875 | 0.8836909288430201 | 112.3954434620202 | 173 |
| `or15_nq15_signed_breakout_1030` | `rescue1` | 0 / 81 | 0 | -400.0 | 0.9788415763025654 | 100.72762182939621 | 168 |

Best original: `or30_nq15_signed_breakout_1030/run1` with top net `-306.25` and PF `0.9890556597873671`.
Best rescue: `or30_nq15_signed_breakout_1030/rescue1` with top net `-33.75` and PF `0.9974446337308348`.

Final decision: FAIL
