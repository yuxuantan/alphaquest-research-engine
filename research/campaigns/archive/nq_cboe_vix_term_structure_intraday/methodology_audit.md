# Methodology Audit - NQ Cboe VIX Term Structure Intraday

Verdict: FAIL. No variant is a candidate strategy.

Scope and timing:
- Five variants were predeclared under one edge: lagged Cboe VIX maturity term-structure state applied to NQ.
- Feature construction used only the latest Cboe VIX9D, VIX, VIX3M, and VIX6M closes strictly before the NQ session date.
- Intraday entries used completed 1-minute NQ RTH bars and next-bar/open-boundary execution handled by the staged engine.
- No NQ rescue, threshold narrowing, exclusion, timeframe change, or mechanics change was made after results.

Gate outcomes:
- `contango_long_1030` passed core but failed the randomized monkey gate.
- `curve_flattening_short_1200` passed core and monkey but failed WFA with negative stitched OOS performance and early exit.
- `front_stress_short_1130` passed core and monkey but failed WFA immediately on in-sample train quality.
- `backwardation_surge_short_1330` and `backwardation_short_1000` failed limited core.

Rejection rationale:
- Core profitability was not stable enough across all variants.
- The variants that survived randomized timing did not survive walk-forward selection on unseen windows.
- Passing core or monkey alone is insufficient for promotion under the staged workflow.

Durable artifacts:
- Aggregate summary: `backtest-campaigns/nq_cboe_vix_term_structure_intraday/campaign_test_summary.json`
- Results CSV: `backtest-campaigns/nq_cboe_vix_term_structure_intraday/campaign_results.csv`
- Density audit: `research_artifacts/nq_cboe_vix_term_structure_intraday_density_audit_20260622.md`
