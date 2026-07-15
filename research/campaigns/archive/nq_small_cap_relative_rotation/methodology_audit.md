# NQ Small-Cap Relative Rotation Methodology Audit

Verdict: FAIL.

This campaign was approved for staged testing only after the pre-PnL density screen. The density audit found 21/21 declared entry-grid rows passing and 5/5 variants passing before any PnL was inspected.

Valid `run2` staged validation failed closed at `limited_core_grid_test` for all five predeclared variants. The preserved `run1` roots are invalid infrastructure attempts caused by a missing entry-module registry mapping and are not PnL evidence.

## Lookahead Controls

- IWM and QQQ daily observations are joined with a one-business-day availability lag.
- Entries fire only after a completed NQ RTH bar at the configured time.
- No same-day ETF close, final NQ high/low, final VWAP, or post-entry path is used.

## Duplicate Check

The edge is not a relabel of the rejected XLK/SPY technology-relative-strength, broad sector-rotation, ES/NQ intraday relative-value, or NQ own-momentum campaigns. It specifically tests small-cap versus Nasdaq-relative rotation through IWM/QQQ.

## Artifacts

- Feature builder: `tools/build_nq_small_cap_relative_features.py`
- Feature CSV: `data/external/nq_small_cap_relative_features_20110103_20260612.csv`
- Density audit: `research_artifacts/nq_small_cap_relative_rotation_density_audit_20260701.md`
- Campaign results: `backtest-campaigns/nq_small_cap_relative_rotation/campaign_results.csv`
- Campaign summary: `backtest-campaigns/nq_small_cap_relative_rotation/campaign_test_summary.json`

Final decision: FAIL. No variant reached monkey testing, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.
