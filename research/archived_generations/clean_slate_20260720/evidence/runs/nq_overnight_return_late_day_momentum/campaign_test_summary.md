# NQ Overnight Return Late-Day Momentum Campaign Summary

Verdict: FAIL.

All five predeclared NQ overnight-return late-day momentum variants failed limited_core_grid_test. Across 162 official core combinations, 0 were profitable, 0 passed benchmark gates, and 0 had Apex rule violations. The least-negative top row was negative_overnight_short_1530 with top net -535.00, PF 0.9335, and 173 trades, so no variant reached monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

Density screen passed before PnL: 27/27 declared entry rows cleared full-history, limited-core, and latest-252 signal-count gates.

| variant | profitable combos | total combos | profitable rate | benchmark pass | top net | top PF | top trades | top failure |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `two_sided_overnight_sign_continuation_1530` | 0 | 18 | 0.000 | 0 | -3135.00 | 0.794 | 333 | min_total_net_profit;max_consecutive_losses |
| `positive_overnight_long_1530` | 0 | 18 | 0.000 | 0 | -2080.00 | 0.730 | 178 | min_total_net_profit;max_consecutive_losses |
| `negative_overnight_short_1530` | 0 | 18 | 0.000 | 0 | -535.00 | 0.934 | 173 | min_total_net_profit |
| `opening_reversal_confirmed_1530` | 0 | 54 | 0.000 | 0 | -1490.00 | 0.762 | 121 | min_total_net_profit |
| `penultimate_alignment_1530` | 0 | 54 | 0.000 | 0 | -1205.00 | 0.759 | 103 | min_total_net_profit |

Campaign results: `backtest-campaigns/nq_overnight_return_late_day_momentum/campaign_results.csv`.
Density audit: `research_artifacts/nq_overnight_return_late_day_momentum_density_audit_20260630.md`.

No candidate strategy report was created.
