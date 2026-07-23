# ES CFTC TFF Hedging Pressure Rescue Attempt 1

Date: 2026-06-15

Decision: FAIL

The rescue kept the shifted CFTC/TFF hedging-pressure mechanic, `SPX_open_interest_chg13` feature, sign, entry time, 5-minute timeframe, 2013-04-15 to 2026-06-09 data window, ES costs, and validation gates fixed. It changed only the CFTC threshold grid plus stop/target grids.

Valid original `run2` and all `rescue1` runs failed `limited_core_grid_test`; no run reached monkey, WFA, Monte Carlo, or frozen validation.

The initial `run1` artifacts are invalidated because the limited-core first-window sample started before non-null shifted CFTC feature coverage and produced zero trades.

Summary artifact: `backtest-campaigns/es_cftc_tff_hedging_pressure/campaign_test_summary.json`.
