# Methodology Audit - NQ VVIX Tail Risk Intraday

Verdict: FAIL. No variant is a candidate strategy.

Scope and timing:
- Five variants were predeclared under one edge: lagged Cboe VVIX/VIX tail-risk state applied to NQ.
- Feature construction used only the latest Cboe VVIX and VIX closes strictly before the NQ session date.
- Intraday entries used completed 1-minute NQ RTH bars and next-bar/open-boundary execution handled by the staged engine.
- No NQ rescue, threshold narrowing, exclusion, timeframe change, or mechanics change was made after results.

Gate outcomes:
- `low_vvix_long_1030` passed core but failed the randomized monkey gate.
- `rising_vvix_short_1130` passed core but failed the randomized monkey gate.
- `high_vvix_short_1000`, `falling_vvix_long_1200`, and `high_vvix_vix_ratio_short_1330` failed limited core.

Rejection rationale:
- Core profitability did not separate strongly from randomized timing for the variants that passed core.
- Three of five edge expressions failed before robustness testing.
- Passing core alone is insufficient for promotion under the staged workflow.

Durable artifacts:
- Aggregate summary: `backtest-campaigns/nq_vvix_tail_risk_intraday/campaign_test_summary.json`
- Results CSV: `backtest-campaigns/nq_vvix_tail_risk_intraday/campaign_results.csv`
- Density audit: `research_artifacts/nq_vvix_tail_risk_intraday_density_audit_20260622.md`
