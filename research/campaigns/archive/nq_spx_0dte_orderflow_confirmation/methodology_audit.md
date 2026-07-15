# Methodology Audit: nq_spx_0dte_orderflow_confirmation

Decision: FAIL

## Scope

- Campaign: `nq_spx_0dte_orderflow_confirmation`
- Source NQ campaign: `nq_spx_0dte_expiration_pressure`
- NQ orderflow cache: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- SPX 0DTE calendar: `data/external/nq_spx_0dte_calendar_sessions_20110103_20260612.csv`
- Density audit: `research_artifacts/nq_spx_0dte_orderflow_confirmation_density_audit_20260623.md`
- Aggregate summary: `backtest-campaigns/nq_spx_0dte_orderflow_confirmation/campaign_test_summary.json`
- Results CSV: `backtest-campaigns/nq_spx_0dte_orderflow_confirmation/campaign_results.csv`

## Integrity Notes

- SPX 0DTE calendar membership is generated from published listing rules and known before each session.
- Open-to-signal move uses only the NQ session open and the completed signal-bar close.
- Orderflow confirmation uses only completed NQ bars in the configured rolling window ending at the signal close.
- Entry is emitted at the signal-bar close and staged execution handles next-bar-or-later fills.
- Stop, target, forced flatten, commission, slippage, tick size, point value, and prop-rule settings are read from config.
- The parameter grid was fixed before PnL testing; no rescue was authorized or attempted.

## Staged Outcome

All five frozen variants failed `limited_core_grid_test`. None reached monkey, WFA, Monte Carlo, or simulated incubation. The full-history density screen was sufficient for pre-PnL selection, but the latest limited-core slice produced too few benchmark-quality opportunities.

- `all_available_1400_signed60_continue`: 0/81 profitable combos, 0/81 benchmark-pass combos, top net -100.0, PF 0.7701149425287356, top trades 7.
- `all_available_1430_signed60_continue`: 15/81 profitable combos, 0/81 benchmark-pass combos, top net 227.5, PF 1.4595959595959596, top trades 8.
- `all_available_1430_signed120_continue`: 30/81 profitable combos, 0/81 benchmark-pass combos, top net 205.0, PF unavailable, top trades 1.
- `all_available_1500_signed60_continue`: 0/81 profitable combos, 0/81 benchmark-pass combos, top net 0.0, PF 0.0, top trades 0.
- `all_available_1515_signed120_continue`: 3/81 profitable combos, 0/81 benchmark-pass combos, top net 165.0, PF unavailable, top trades 1.

No `candidate_strategy_report.md` was created.
