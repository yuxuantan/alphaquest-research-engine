# Methodology Audit - NQ Cboe VIX Level State Intraday

Verdict: FAIL. No variant is a candidate strategy.

Scope and timing:
- Five variants were predeclared under one edge: lagged Cboe VIX level/change state applied to NQ.
- Feature construction used only the latest Cboe VIX close strictly before the NQ session date.
- Intraday entries used completed 1-minute NQ RTH bars and next-bar/open-boundary execution handled by the staged engine.
- No NQ rescue, threshold narrowing, exclusion, timeframe change, or mechanics change was made after results.

Gate outcomes:
- `vix_spike_riskoff_short_1130` passed core but failed the randomized monkey gate on drawdown robustness.
- `high_vix_rebound_long_1000`, `low_vix_complacency_short_1030`, `vix_crush_rebound_long_1200`, and `persistent_high_vix_long_1330` failed limited core.

Rejection rationale:
- The only strong core expression did not survive randomized timing/drawdown comparison.
- Four of five edge expressions failed before robustness testing.
- This confirms that broad VIX state alone is not enough for NQ staged promotion here.

Durable artifacts:
- Aggregate summary: `backtest-campaigns/nq_cboe_vix_level_state_intraday/campaign_test_summary.json`
- Results CSV: `backtest-campaigns/nq_cboe_vix_level_state_intraday/campaign_results.csv`
- Density audit: `research_artifacts/nq_cboe_vix_level_state_intraday_density_audit_20260622.md`
