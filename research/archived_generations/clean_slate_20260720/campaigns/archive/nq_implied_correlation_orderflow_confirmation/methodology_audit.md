# Methodology Audit: nq_implied_correlation_orderflow_confirmation

Decision: FAIL

## Scope

- Campaign: `nq_implied_correlation_orderflow_confirmation`
- Feature file: `data/external/nq_cboe_implied_correlation_features_20110103_20260612.csv`
- NQ cache: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Density audit: `research_artifacts/nq_implied_correlation_orderflow_confirmation_density_audit_20260623.md`
- Aggregate summary: `backtest-campaigns/nq_implied_correlation_orderflow_confirmation/campaign_test_summary.json`
- Results CSV: `backtest-campaigns/nq_implied_correlation_orderflow_confirmation/campaign_results.csv`

## Integrity Notes

- Cboe implied-correlation features are lagged before the NQ session date.
- Same-session NQ orderflow confirmation uses only completed RTH bars through the configured signal close.
- Entry is emitted at the signal-bar close and the staged engine handles next-bar-or-later execution.
- Stop, target, forced flatten, commission, slippage, tick size, point value, and prop-rule settings are read from config.
- The frozen parameter grid was not changed after staged results were observed.
- No rescue was authorized or attempted.

## Staged Outcome

All five frozen variants failed the staged validation flow.

- `rising_corr_1330_large20_flow_short` failed limited_core_grid_test.
- `rising_corr_1330_signed_flow_short` failed limited_core_grid_test.
- `shortterm_corr_1330_large20_flow_short` passed limited core and monkey, then failed walk_forward_analysis with 0.0 profitable-window rate and stitched OOS net -2900.0.
- `shortterm_corr_1330_signed_flow_short` passed limited core and monkey, then failed walk_forward_analysis with 0.6 profitable-window rate, stitched OOS net -21280.0, PF 0.8877, and max drawdown pct 0.2475.
- `shortterm_corr_1200_signed_flow_short` passed limited core, then failed limited_monkey_test.

No WFA survivor reached WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, acceptance, or candidate reporting. No `candidate_strategy_report.md` was created.
