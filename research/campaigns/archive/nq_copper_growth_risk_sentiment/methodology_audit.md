# NQ Copper Growth/Risk Sentiment Methodology Audit

Verdict: FAIL.

This campaign was approved for staged testing only after the pre-PnL density screen. The density audit found 45/45 declared entry-grid rows passing and 5/5 variants passing before any PnL was inspected.

Staged validation failed closed. All five variants failed `limited_core_grid_test`; no branch reached `limited_monkey_test`, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

## Lookahead Controls

- HG=F and GC=F daily observations are joined with a one-calendar-day availability lag.
- Rolling ranks are computed before the session-level as-of join.
- Entries fire only after a completed NQ RTH bar at the configured time.
- No same-day commodity close, final NQ high/low, final VWAP, or post-entry path is used.

## Duplicate Check

The edge is not a relabel of crypto risk sentiment, small-cap rotation, Europe/Tokyo equity spillover, FX/oil shock, precious-metals tail risk, VIX/VVIX/variance state, ES/NQ relative value, sector, or NQ own-momentum campaigns. It specifically tests industrial-metals growth/risk sentiment through lagged copper return and copper/gold ratio ranks.

## Source Caveat

CME OpenMarkets treats copper as an economic-health indicator but explicitly warns that copper's linkage to stock-market performance is unstable. This campaign was therefore expected to fail unless it survived broad parameter stability and robustness gates.

## Artifacts

- Feature builder: `tools/build_nq_copper_growth_risk_sentiment_features.py`
- Feature CSV: `data/external/nq_copper_growth_risk_sentiment_features_20110103_20260612.csv`
- Density audit: `research_artifacts/nq_copper_growth_risk_sentiment_density_audit_20260701.md`
- Campaign results: `backtest-campaigns/nq_copper_growth_risk_sentiment/campaign_results.csv`
- Campaign summary: `backtest-campaigns/nq_copper_growth_risk_sentiment/campaign_test_summary.json`

Final decision: FAIL. No candidate strategy report was written.
