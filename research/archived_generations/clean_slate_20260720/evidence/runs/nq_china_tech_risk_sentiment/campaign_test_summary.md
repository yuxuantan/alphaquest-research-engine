# NQ China Tech Risk Sentiment Campaign Summary

Decision: FAIL

Three variants failed limited_core_grid_test by profitable-iteration breadth; two variants passed core and monkey but failed walk_forward_analysis with early exits and negative stitched OOS metrics. No branch reached WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

ChartFanatics gate: no additional nonduplicate ES/NQ ChartFanatics-derived campaign was eligible under current data and no-duplicate rules; see `research_artifacts/chartfanatics_remaining_strategy_source_gate_after_nq_jobless_claims_20260701.md`.

| Variant | Terminal Stage | Core Profitable Rate | Benchmark Pass | Top Net | Fixed Net | Monkey Net Beat | WFA Net | WFA PF | WFA MAR |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| cqqq_1d_relative_strength_long_1000 | walk_forward_analysis | 0.925926 | 20/27 | 8640 | 2775 | 0.95975 | -2215 | 0.895887 | -0.65992 |
| cqqq_3d_relative_weakness_short_1030 | limited_core_grid_test | 0.592593 | 6/27 | 5002.5 | 865 |  |  |  |  |
| fxi_1d_relative_strength_long_1130 | limited_core_grid_test | 0 | 0/27 | -200 | -1415 |  |  |  |  |
| fxi_3d_relative_weakness_short_1200 | limited_core_grid_test | 0.555556 | 1/27 | 1380 | 200 |  |  |  |  |
| cqqq_1d_volatility_short_1330 | walk_forward_analysis | 1 | 23/27 | 3752.5 | 3270 | 0.98175 | -6645 | 0.899127 | -0.14337 |
