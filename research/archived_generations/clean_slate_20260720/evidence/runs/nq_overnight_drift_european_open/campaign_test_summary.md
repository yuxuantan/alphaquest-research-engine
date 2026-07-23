# NQ Overnight Drift European Open Campaign Summary

Verdict: FAIL.

All five predeclared variants failed `limited_core_grid_test`; no WFA, monkey, Monte Carlo, simulated incubation, or acceptance stage was reached.

| variant | combos | profitable | benchmark pass | top net | top PF | top trades/year | top failure |
|---|---:|---:|---:|---:|---:|---:|---|
| eu_open_down_no_recovery_long_0200 | 54 | 0 | 0 | -510.00 | 0.8850 | 94.09 | min_total_net_profit |
| eu_open_prior_down_long_0200 | 27 | 0 | 0 | -1195.00 | 0.7534 | 114.34 | min_total_net_profit |
| eu_open_prior_down_long_0230 | 27 | 0 | 0 | -507.50 | 0.9306 | 114.34 | min_total_net_profit |
| eu_open_unconditional_long_0200 | 9 | 0 | 0 | -2950.00 | 0.7079 | 246.10 | min_total_net_profit |
| london_open_prior_down_long_0300 | 27 | 0 | 0 | -1162.50 | 0.8717 | 114.35 | min_total_net_profit |

Best top core row by net profit: `eu_open_prior_down_long_0230` with net `-507.50` and PF `0.9306`.

No `candidate_strategy_report.md` was created because nothing passed.
