# NQ Session-Extreme Cumulative-Delta Divergence Campaign Summary

Verdict: FAIL.

All five predeclared NQ session-extreme delta-divergence variants failed limited_core_grid_test. Across 60 official core combinations, only 1 was profitable, 0 passed benchmark gates, and 0 had Apex rule violations. The only profitable row was afternoon_high_delta_divergence_short with top net 150.0 but it failed max_best_day_concentration, so no variant reached monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

Density screen passed before PnL: 20/20 declared entry rows cleared full-history, limited-core, and latest-252 signal-count gates.

| variant | profitable combos | total combos | profitable rate | benchmark pass | top net | top PF | top trades | top failure |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `afternoon_high_delta_divergence_short` | 1 | 12 | 0.083 | 0 | 150.00 | 1.022 | 133 | max_best_day_concentration |
| `afternoon_low_delta_divergence_long` | 0 | 12 | 0.000 | 0 | -2145.00 | 0.432 | 103 | min_total_net_profit;max_consecutive_losses |
| `midday_two_sided_delta_divergence` | 0 | 12 | 0.000 | 0 | -6275.00 | 0.427 | 293 | min_total_net_profit;max_consecutive_losses |
| `morning_high_delta_divergence_short` | 0 | 12 | 0.000 | 0 | -5045.00 | 0.693 | 224 | min_total_net_profit |
| `morning_low_delta_divergence_long` | 0 | 12 | 0.000 | 0 | -3425.00 | 0.531 | 213 | min_total_net_profit |

Campaign results: `backtest-campaigns/nq_session_extreme_delta_divergence/campaign_results.csv`.
Density audit: `research_artifacts/nq_session_extreme_delta_divergence_density_audit_20260630.md`.

No candidate strategy report was created.
