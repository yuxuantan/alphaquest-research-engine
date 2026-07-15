# Methodology Audit: nq_tech_nonleadership_orderflow_confirmation

Decision: FAIL

## Scope

- Campaign: `nq_tech_nonleadership_orderflow_confirmation`
- Feature file: `data/external/nq_tech_relative_strength_features_20110103_20260612.csv`
- NQ cache: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Density audit: `research_artifacts/nq_tech_nonleadership_orderflow_confirmation_density_audit_20260623.md`
- Aggregate summary: `backtest-campaigns/nq_tech_nonleadership_orderflow_confirmation/campaign_test_summary.json`
- Results CSV: `backtest-campaigns/nq_tech_nonleadership_orderflow_confirmation/campaign_results.csv`

## Integrity Notes

- XLK/SPY feature availability is lagged by one business day before the NQ session date.
- Same-session confirmation uses only completed NQ RTH bars through the configured signal close.
- Entry is emitted at the signal-bar close and the staged engine handles next-bar-or-later execution.
- Stop, target, and forced flatten are read from config and were not changed after results.
- The broad `rank_max=0.60` grid value is labelled non-leadership, not lower-tail weakness.

## Staged Outcome

All five frozen NQ tech non-leadership/orderflow-confirmation variants failed limited_core_grid_test. No run reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, acceptance, or candidate reporting.

No `candidate_strategy_report.md` was created.
