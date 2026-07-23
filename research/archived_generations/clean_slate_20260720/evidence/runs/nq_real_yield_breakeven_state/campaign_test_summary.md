# NQ Real-Yield and Breakeven State Test Summary

Verdict: FAIL

The campaign passed the pre-PnL density gate (15/15 declared density rows) and all five variants were run through the staged validator. No variant reached WFA or acceptance OOS.

Failure summary:
- Four variants failed `limited_core_grid_test`.
- `breakeven_1d_up_long_1000` passed `limited_core_grid_test` but failed `limited_monkey_test`: net-profit beat rate 0.8845 and max-drawdown beat rate 0.795125, below the 0.90 threshold.
- No rescue was authorized or attempted.

| Variant | Terminal Stage | Top Net | Top PF | Top Trades | Top MAR | Failure |
|---|---:|---:|---:|---:|---:|---|
| `breakeven_1d_up_long_1000` | `limited_monkey_test` | 1642.5 | 1.1659929257200607 | 143 | 0.5754245780872949 | summary.core_beats_monkey_net_profit_rate actual=0.8845 expected={'min': 0.9}; summary.core_beats_monkey_max_drawdown_rate actual=0.795125 expected={'min': 0.9} |
| `breakeven_5d_down_short_1130` | `limited_core_grid_test` | -297.5 | 0.9770801232665639 | 123 | -0.08385796178018694 | summary.percentage_profitable_iterations actual=0.0 expected={'min': 0.7} |
| `real_yield_1d_down_long_1000` | `limited_core_grid_test` | 310.0 | 1.0208473436449226 | 160 | 0.1173952928312077 | summary.percentage_profitable_iterations actual=0.16666666666666666 expected={'min': 0.7} |
| `real_yield_1d_up_short_1000` | `limited_core_grid_test` | -1010.0 | 0.9114811568799299 | 120 | -0.2956368092558199 | summary.percentage_profitable_iterations actual=0.0 expected={'min': 0.7} |
| `real_yield_5d_up_short_1130` | `limited_core_grid_test` | -2175.0 | 0.8526422764227642 | 141 | -0.40268309607153163 | summary.percentage_profitable_iterations actual=0.0 expected={'min': 0.7} |

Artifacts:
- Results CSV: `backtest-campaigns/nq_real_yield_breakeven_state/campaign_results.csv`
- Summary JSON: `backtest-campaigns/nq_real_yield_breakeven_state/campaign_test_summary.json`
- Density audit: `research_artifacts/nq_real_yield_breakeven_state_density_audit_20260630.md`
