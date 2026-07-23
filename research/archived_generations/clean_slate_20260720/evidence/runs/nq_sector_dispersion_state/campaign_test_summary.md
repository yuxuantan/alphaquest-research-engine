# Campaign Test Summary: nq_sector_dispersion_state

Verdict: FAIL

All five variants failed `limited_core_grid_test`; no monkey, WFA, Monte Carlo, simulated incubation, or acceptance OOS stage was reached. The best pocket is rejected because it did not meet the profitable-combo-rate gate.

| variant | profitable combos | benchmark-pass combos | top net | top PF | top trades | top MAR | failure |
|---|---:|---:|---:|---:|---:|---:|---|
| `rising_1d_dispersion_short_1130` | 17/27 | 13 | 4845.0 | 1.3298162014976174 | 129 | 1.0461770255400704 | profitable-combo rate below 0.70 gate |
| `high_5d_dispersion_short_1030` | 8/27 | 0 | 1507.5 | 1.1187007874015749 | 107 | 0.4768754587241516 | max_consecutive_losses |
| `falling_5d_dispersion_long_1330` | 2/27 | 0 | 85.0 | 1.0099183197199533 | 106 | 0.037800224744783006 | max_best_day_concentration |
| `high_1d_dispersion_short_1000` | 0/27 | 0 | -2500.0 | 0.7467071935157041 | 94 | -0.4789291170058035 | min_total_net_profit;max_consecutive_losses |
| `low_1d_dispersion_long_1200` | 0/18 | 0 | -152.5 | 0.9888196480938416 | 134 | -0.03441238000094031 | min_total_net_profit |

Density audit: `research_artifacts/nq_sector_dispersion_state_density_audit_20260623.md`
Detailed results CSV: `backtest-campaigns/nq_sector_dispersion_state/campaign_results.csv`
