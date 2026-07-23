# NQ Manufacturing Orders State Campaign Summary

Decision: FAIL

All five variants failed limited_core_grid_test; 4 variants had profitable top cells, but no variant met the 0.70 profitable-iteration stability threshold. No branch reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Terminal Stage | Core Profitable Rate | Benchmark Pass | Top Net | Fixed Net | Monkey Net Beat | Monkey DD Beat |
|---|---|---:|---:|---:|---:|---:|---:|
| core_capgoods_3m_strength_long_1130 | limited_core_grid_test | 0.037037037037037035 | 0/27 | 275.0 | -3405.0 |  |  |
| durables_1m_weakness_short_1200 | limited_core_grid_test | 0.1111111111111111 | 0/27 | 540.0 | -1192.5 |  |  |
| ex_transport_3m_strength_long_1330 | limited_core_grid_test | 0.0 | 0/27 | -900.0 | -1447.5 |  |  |
| total_orders_3m_strength_long_1000 | limited_core_grid_test | 0.5185185185185185 | 8/27 | 1770.0 | 960.0 |  |  |
| total_orders_3m_weakness_short_1030 | limited_core_grid_test | 0.2222222222222222 | 6/27 | 2665.0 | -3275.0 |  |  |
