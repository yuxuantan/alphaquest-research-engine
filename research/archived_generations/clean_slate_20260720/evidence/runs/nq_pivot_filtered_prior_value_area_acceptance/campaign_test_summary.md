# Campaign Test Summary: nq_pivot_filtered_prior_value_area_acceptance

Verdict: FAIL

All five variants failed limited_core_grid_test. Best profitable-rate was midday_signed_two_sided_pivot_acceptance at 34/54 (0.6296296296296297), below the 0.70 gate. Across all official variants, 89/270 combinations were profitable, 39 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Profitable / Total | Profitable Rate | Benchmark Pass | Top Net | Top PF | Apex Violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| afternoon_large20_two_sided_pivot_acceptance | 15/54 | 0.277778 | 11 | 1095.0 | 1.2236976506639428 | 0 |
| late_morning_large10_two_sided_pivot_acceptance | 15/54 | 0.277778 | 7 | 1320.0 | 1.118067978533095 | 0 |
| midday_signed_two_sided_pivot_acceptance | 34/54 | 0.629630 | 21 | 1520.0 | 1.1666666666666667 | 0 |
| morning_signed_two_sided_pivot_acceptance_1230 | 3/54 | 0.055556 | 0 | 400.0 | 1.036330608537693 | 0 |
| morning_signed_vah_pivot_acceptance_long | 22/54 | 0.407407 | 0 | 850.0 | 1.1256467110125647 | 0 |

No candidate_strategy_report.md was created because no variant passed all staged tests.
