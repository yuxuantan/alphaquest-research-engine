# NQ Europe Equity Close Spillover Methodology Audit

Verdict: FAIL.

This campaign was approved for staged testing only after the pre-PnL density screen. The density audit found 45/45 declared entry-grid rows passing and 5/5 variants passing before any PnL was inspected.

Staged validation failed closed at `limited_core_grid_test` for all five predeclared variants. `stoxx_1d_weakness_short_1400` had benchmark-passing cells, but its profitable iteration rate was below the required 0.70 stability threshold.

## Lookahead Controls

- Same-day DAX and Euro STOXX 50 observations are used only after the conservative 13:30 ET availability cutoff.
- Days without a same-day European index observation generate no signal; no stale prior-day fill is used.
- Entries fire only after a completed NQ RTH bar at the configured time.
- No final NQ high/low, final VWAP, or post-entry path is used.

## Duplicate Check

The edge is not a relabel of NQ European-open overnight drift, Nikkei/Tokyo close spillover, USDJPY/oil shock spillover, ES/NQ intraday relative value, or NQ own-momentum campaigns. It specifically tests same-day European cash equity close spillover after the European indexes have closed.

## Artifacts

- Feature builder: `tools/build_nq_europe_equity_close_spillover_features.py`
- Feature CSV: `data/external/nq_europe_equity_close_spillover_features_20110103_20260612.csv`
- Density audit: `research_artifacts/nq_europe_equity_close_spillover_density_audit_20260701.md`
- Campaign results: `backtest-campaigns/nq_europe_equity_close_spillover/campaign_results.csv`
- Campaign summary: `backtest-campaigns/nq_europe_equity_close_spillover/campaign_test_summary.json`

Final decision: FAIL. No variant reached monkey testing, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.
