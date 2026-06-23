# NQ Overnight Drift European Open Methodology Audit

Verdict: FAIL.

The campaign was authored as a fresh NQ-only ETH-session test after the
transfer-first ES/NQ candidates were exhausted. It reused the existing
`overnight_drift` entry module and tested exactly five variants:

- `eu_open_unconditional_long_0200`
- `eu_open_prior_down_long_0200`
- `eu_open_down_no_recovery_long_0200`
- `eu_open_prior_down_long_0230`
- `london_open_prior_down_long_0300`

Pre-PnL density used only fixed ETH clocks, prior completed RTH fields, and
completed ETH-bar state. The sparse `max_pre_signal_return_ticks: 0` corner was
rejected before PnL for the recovery-filtered variant. The staged configs then
used only the declared grid and no rescue.

All five variants failed `limited_core_grid_test` with zero profitable
combinations and zero benchmark-pass combinations. The best top core-grid row
was `eu_open_prior_down_long_0230`, net `-507.50`, PF `0.9306`, 175 trades, and
114.34 trades/year over the shortlist window. Apex violations were zero, so the
rejection is economic, not a forced-flatten mechanics failure.

No limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or
acceptance stage was reached. No `candidate_strategy_report.md` was created.

Primary generated artifacts:

- `backtest-campaigns/nq_overnight_drift_european_open/campaign_test_summary.json`
- `backtest-campaigns/nq_overnight_drift_european_open/campaign_results.csv`
- `backtest-campaigns/nq_overnight_drift_european_open/trade_logs_manifest.csv`
- `backtest-campaigns/nq_overnight_drift_european_open/equity_curves_manifest.csv`
- `backtest-campaigns/nq_overnight_drift_european_open/wfa_table.csv`
- `backtest-campaigns/nq_overnight_drift_european_open/monte_carlo_summary.csv`
