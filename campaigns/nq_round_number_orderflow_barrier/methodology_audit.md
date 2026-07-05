# NQ Round-Number Orderflow Barrier Methodology Audit

Verdict: FAIL

Completed: 2026-06-30T20:30:00+08:00

The campaign was eligible for staged testing only after the declared pre-PnL density screen passed all official entry rows: `research_artifacts/nq_round_number_orderflow_barrier_density_audit_20260630.md`.

All five predeclared variants then failed `limited_core_grid_test`. The official failure condition was parameter-neighborhood instability: the best variant-level profitable iteration rate was `24/54 = 0.444444`, below the required `0.70` threshold. Across all five variants, `54/270 = 0.200000` combinations were profitable and `37/270 = 0.137037` passed the benchmark row checks.

No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting. The strongest top rows are rejected as isolated parameter pockets, not candidate strategies.

No rescue was run. The campaign explicitly disallowed post-result mechanics changes, and selecting only the profitable top rows would violate the predeclared parameter-space discipline.

Artifacts:

- `backtest-campaigns/nq_round_number_orderflow_barrier/campaign_test_summary.json`
- `backtest-campaigns/nq_round_number_orderflow_barrier/campaign_test_summary.md`
- `backtest-campaigns/nq_round_number_orderflow_barrier/campaign_results.csv`
- `backtest-campaigns/nq_round_number_orderflow_barrier/trade_logs_manifest.csv`
- `backtest-campaigns/nq_round_number_orderflow_barrier/equity_curves_manifest.csv`
- `backtest-campaigns/nq_round_number_orderflow_barrier/wfa_table.csv`
- `backtest-campaigns/nq_round_number_orderflow_barrier/wfa_oos_trade_log.csv`
- `backtest-campaigns/nq_round_number_orderflow_barrier/monte_carlo_summary.json`
