# Campaign Test Summary: nq_epu_policy_uncertainty_intraday

Verdict: FAIL

All five variants failed `limited_core_grid_test`; no monkey, WFA, Monte Carlo, simulated incubation, or acceptance OOS stage was reached. Positive pockets are logged as rejected evidence, not promoted.

| variant | profitable combos | benchmark-pass combos | top net | top PF | top trades | top MAR | failure |
|---|---:|---:|---:|---:|---:|---:|---|
| `low_epu_long_1030` | 5/9 | 4 | 2107.5 | 1.1582207207207207 | 124 | 1.0698317432340791 | profitable-combo rate below 0.70 gate |
| `rising_epu_short_1130` | 8/27 | 5 | 4385.0 | 1.2568081991215228 | 148 | 0.70145649014758 | profitable-combo rate below 0.70 gate |
| `high_epu_short_1000` | 0/27 | 0 | -1825.0 | 0.43146417445482865 | 89 | -0.6754967762591618 | min_total_net_profit;max_consecutive_losses |
| `falling_epu_long_1200` | 0/18 | 0 | -2126.25 | 0.8319169960474309 | 110 | -0.35206370920017316 | min_total_net_profit;max_consecutive_losses |
| `high_epu_ma_short_1330` | 0/18 | 0 | -1580.0 | 0.5413642960812772 | 104 | -0.8226423911962587 | min_total_net_profit |

Density audit: `research_artifacts/nq_epu_policy_uncertainty_intraday_density_audit_20260623.md`
Detailed results CSV: `backtest-campaigns/nq_epu_policy_uncertainty_intraday/campaign_results.csv`
