# NQ Prior-Session IBS Reversion Campaign Summary

Decision: FAIL

All five variants failed limited_core_grid_test. Best profitable-rate was delayed_low_ibs_long_range_filtered at 6/9 (0.6666666666666666), below the 0.70 gate. Across all official variants, 56/171 combinations were profitable, 17 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Profitable combos | Profitable rate | Benchmark pass | Top net | Top PF | Top trades |
|---|---:|---:|---:|---:|---:|---:|
| `open_low_ibs_long` | 3/9 | 0.333333 | 1 | 1490.00 | 1.147015 | 84 |
| `open_high_ibs_short` | 13/36 | 0.361111 | 3 | 2270.00 | 1.217746 | 81 |
| `open_two_sided_ibs_reversion` | 13/81 | 0.160494 | 5 | 3385.00 | 1.176394 | 165 |
| `delayed_low_ibs_long_range_filtered` | 6/9 | 0.666667 | 3 | 1025.00 | 1.155068 | 84 |
| `delayed_high_ibs_short_range_filtered` | 21/36 | 0.583333 | 5 | 2772.50 | 1.288953 | 81 |

No candidate_strategy_report.md was created because no variant passed limited core.
