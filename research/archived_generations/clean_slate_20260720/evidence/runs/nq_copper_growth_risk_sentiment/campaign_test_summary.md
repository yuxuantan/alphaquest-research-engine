# NQ Copper Growth/Risk Sentiment Campaign Summary

Final decision: FAIL.

All five predeclared variants failed `limited_core_grid_test`. No variant reached monkey robustness, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Stage | Benchmark Pass | Profitable Rate | Top Net | Top PF | Fixed Net | Fixed PF |
|---|---|---:|---:|---:|---:|---:|---:|
| copper_1d_strength_long_1000 | limited_core_grid_test | 3/27 | 0.629630 | 2055.00 | 1.108501 | -285.00 | 0.983270 |
| copper_1d_weakness_short_1000 | limited_core_grid_test | 11/27 | 0.666667 | 3535.00 | 1.168816 | 3355.00 | 1.153512 |
| copper_3d_strength_long_1030 | limited_core_grid_test | 3/27 | 0.333333 | 1920.00 | 1.140608 | -2415.00 | 0.856974 |
| copper_gold_ratio_strength_long_1130 | limited_core_grid_test | 0/27 | 0.259259 | 352.50 | 1.031530 | -55.00 | 0.996335 |
| copper_gold_ratio_weakness_short_1330 | limited_core_grid_test | 1/27 | 0.222222 | 1382.50 | 1.116963 | -1015.00 | 0.939057 |

Density audit passed before PnL: 45/45 rows, 5/5 variants.

No rescue attempt was authorized or run.
