# NQ Trade-Size Segmented Stealth Orderflow Campaign Summary

Decision: FAIL

All five variants failed limited_core_grid_test. Best profitable-rate was large20_not_aligned_long_1000 at 45/81 (0.5555555555555556), below the 0.70 gate. Across all official variants, 98/405 combinations were profitable, 16 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Profitable combos | Profitable rate | Benchmark pass | Top net | Top PF | Top trades |
|---|---:|---:|---:|---:|---:|---:|
| `large20_not_aligned_long_1000` | 45/81 | 0.555556 | 1 | 360.00 | 1.090794 | 78 |
| `large20_loose_short_1030` | 18/81 | 0.222222 | 9 | 1195.00 | 1.129750 | 163 |
| `large10_loose_long_1130` | 0/81 | 0.000000 | 0 | -1695.00 | 0.794296 | 156 |
| `large10_loose_short_1230` | 0/81 | 0.000000 | 0 | -2230.00 | 0.744413 | 143 |
| `large20_opposite_two_sided_1400` | 35/81 | 0.432099 | 6 | 1165.00 | 1.136817 | 159 |

No candidate_strategy_report.md was created because no variant passed limited core.
