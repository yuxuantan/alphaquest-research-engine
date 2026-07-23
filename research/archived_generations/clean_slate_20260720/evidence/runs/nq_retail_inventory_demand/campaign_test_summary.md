# NQ Retail Inventory Demand Campaign Summary

Decision: FAIL

All five variants failed limited_core_grid_test; two variants had profitable top cells, but no variant met the 0.70 profitable-iteration stability threshold. No branch reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Terminal Stage | Core Profitable Rate | Benchmark Pass | Top Net | Fixed Net | Monkey Net Beat | Monkey DD Beat |
|---|---|---:|---:|---:|---:|---:|---:|
| inventory_sales_falling_long_1330 | limited_core_grid_test | 0.0 | 0/27 | -415.0 | -2015.0 |  |  |
| inventory_sales_low_long_1200 | limited_core_grid_test | 0.0 | 0/27 | -2437.5 | -3497.5 |  |  |
| retail_1m_strength_long_1130 | limited_core_grid_test | 0.0 | 0/27 | -780.0 | -3737.5 |  |  |
| retail_3m_strength_short_1030 | limited_core_grid_test | 0.2222222222222222 | 1/27 | 1310.0 | -1885.0 |  |  |
| retail_3m_weakness_long_1000 | limited_core_grid_test | 0.4444444444444444 | 9/27 | 2450.0 | 1047.5 |  |  |
