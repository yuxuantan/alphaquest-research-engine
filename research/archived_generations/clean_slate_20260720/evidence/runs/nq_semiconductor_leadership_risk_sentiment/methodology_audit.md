# NQ Semiconductor Leadership Methodology Audit

Final decision: FAIL.

The campaign used one-business-day-lagged SMH/SOXX/QQQ daily features. The latest NQ session in the feature cache, 2026-06-12, used ETF observations through 2026-06-11. Signals were generated from completed NQ 1-minute bars and flattened at 15:55 ET.

Duplicate-edge assessment: high risk. This is not an exact duplicate of the failed broad XLK/SPY technology leadership campaigns, but it is close enough that any weak or partial result is rejected rather than rescued.

Pre-PnL density passed 45/45 declared rows: `research_artifacts/nq_semiconductor_leadership_density_audit_20260701.md`.

Four variants failed limited_core_grid_test; soxx_3d_nonleadership_short_1330 passed limited core but failed limited_monkey_test. No branch reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

No candidate_strategy_report.md was written because no variant passed the full staged series.
