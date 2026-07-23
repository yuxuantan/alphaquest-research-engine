# NQ Small-Cap Relative Rotation Campaign Summary

Decision: FAIL

Run2 is the valid staged evidence. Run1 is preserved only as an infrastructure-error retry caused by a missing `ENTRY_MODULES` registry mapping.

| Variant | Terminal Stage | Core Profitable Rate | Benchmark Pass Combos | Top Net | Top PF | Fixed Net | Fixed PF | Top Failure |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| iwm_1d_strength_long_1000 | limited_core_grid_test | 0.407407 | 0/27 | 2870.00 | 1.146354 | -990.00 | 0.948837 | max_consecutive_losses |
| iwm_1d_weakness_short_1000 | limited_core_grid_test | 0.111111 | 0/27 | 1055.00 | 1.044235 | -1530.00 | 0.932346 | max_consecutive_losses;max_best_day_concentration |
| iwm_5d_strength_long_1030 | limited_core_grid_test | 0.000000 | 0/27 | -1135.00 | 0.912993 | -4610.00 | 0.772850 | min_total_net_profit |
| iwm_5d_weakness_short_1130 | limited_core_grid_test | 0.000000 | 0/27 | -630.00 | 0.962788 | -1545.00 | 0.917446 | min_total_net_profit |
| iwm_attention_strength_long_1330 | limited_core_grid_test | 0.197531 | 0/81 | 897.50 | 1.125612 | -645.00 | 0.929392 | max_best_day_concentration |

All five variants stopped at limited_core_grid_test. No variant reached limited monkey testing, WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.
