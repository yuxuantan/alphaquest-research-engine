# Manual Due Diligence Checklist

Audit date: 2026-06-15

Status: BLOCKED - no ES candidate strategy passed the staged methodology in this run.

## Gate Before Chart Review

- Confirm `methodology_audit.md` final decision is PASS.
- Confirm `campaign_test_summary.json` has `passed=true`.
- Confirm the strategy has a `candidate_strategy_report.md`.
- Confirm final acceptance OOS PF, MAR, expectancy, trade count, and Apex-rule checks passed.
- Confirm random-placebo monkey paths and actual-trade perturbation stress paths are each at least 80% profitable with positive median net profit, and confirm the one-tick-worse slippage path remains profitable.

Current result: do not proceed. The active `es_mes_micro_flow_divergence_reversion`, `es_prior_session_ibs_reversion`, `es_connors_rsi2_mean_reversion`, `es_range_compression_breakout`, `es_rth_intraday_risk_premium`, `es_overnight_intraday_reversal`, and `es_signed_orderflow_persistence` campaigns failed before WFA, and all active failed variants have consumed their one allowed rescue without passing.

Current continuation gate: archived tests are ignored when checking duplicate edges. The next campaign must avoid the currently active rejected edge families, but it is not blocked solely because a similar archived test exists. The retained external-data branches still require approval for longer ES+MES `trades` history or a bounded ES `tbbo` liquidity-sweep pilot. No paid data was pulled in this run.

Supporting audit: `research_artifacts/local_no_duplicate_data_gate_audit_20260615.md`.

## Required If A Future Candidate Passes

- Review every WFA OOS and acceptance trade on a chart with timestamp, setup bar, entry bar, stop, target, and flatten time visible.
- Verify no entry uses information unavailable at signal time.
- Check all stop/target same-bar conflicts and confirm pessimistic handling or detail-data resolution.
- Check trade distribution by year, month, session time, and side.
- Check largest winning day/trade contribution and remove any candidate dominated by one event.
- Check prop-rule logs for latest-entry, forced-flatten, no-overnight, and drawdown compliance.
- Paper/incubate only after manual review; do not treat any backtest pass as ready to trade.
