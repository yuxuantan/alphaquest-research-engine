# NQ Intraday Periodicity Orderflow Confirmation Methodology Audit

Verdict: FAIL.

The campaign was authored as a fresh NQ-specific test after transfer-first and
existing NQ orderflow/seasonality branches were exhausted. It reused the
existing `intraday_periodicity_orderflow_confirmation` entry module and tested
exactly five variants:

- `morning_1000_signed_confirmed_slot`
- `morning_1030_large10_confirmed_slot`
- `late_morning_1130_signed_confirmed_slot`
- `afternoon_1330_large20_confirmed_slot`
- `late_afternoon_1430_large20_confirmed_slot`

Pre-PnL density used only prior-session same-clock feature values and completed
pre-entry NQ aggregate orderflow. The sparse `min_orderflow_imbalance: 0.02`
corner was rejected before PnL for the 10:00 signed-flow variant. The staged
configs then used only the declared grid and no rescue.

All five variants failed `limited_core_grid_test`. Across 270 tested core-grid
combinations, 7 were profitable and 0 passed the benchmark gate. The best top
core-grid row was `afternoon_1330_large20_confirmed_slot`, net `657.50`, PF
`1.0974`, 172 trades, and 112.19 trades/year, but it failed
`max_best_day_concentration`. Apex violations were zero, so the rejection is
economic and robustness-related, not a forced-flatten mechanics failure.

No limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or
acceptance stage was reached. No `candidate_strategy_report.md` was created.

Primary generated artifacts:

- `backtest-campaigns/nq_intraday_periodicity_orderflow_confirmation/campaign_test_summary.json`
- `backtest-campaigns/nq_intraday_periodicity_orderflow_confirmation/campaign_results.csv`
- `backtest-campaigns/nq_intraday_periodicity_orderflow_confirmation/trade_logs_manifest.csv`
- `backtest-campaigns/nq_intraday_periodicity_orderflow_confirmation/equity_curves_manifest.csv`
- `backtest-campaigns/nq_intraday_periodicity_orderflow_confirmation/wfa_table.csv`
- `backtest-campaigns/nq_intraday_periodicity_orderflow_confirmation/monte_carlo_summary.csv`
