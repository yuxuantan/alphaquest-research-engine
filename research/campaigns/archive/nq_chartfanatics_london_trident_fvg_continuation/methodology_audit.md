# NQ ChartFanatics London Trident FVG Continuation Methodology Audit

Verdict: FAIL.

The campaign was rejected before staged PnL. The declared five-variant NQ London-session Trident/FVG continuation grid produced 0 passing density rows out of 45. The best variant produced only 2.7272 full-history signals per year and at most 1 signal in the latest 252 sessions, far below the 50 signals/year and latest-252 minimum gates.

No PnL was inspected. No parameter rescue is authorized.

## Source And Edge

Primary source: ChartFanatics Unique High RR, TG Capital, https://www.chartfanatics.com/strategies/unique-high-rr.

Local expression: 30-minute NQ ETH bars, FVG third candle starting 02:30-04:00 ET, stacked 5/9/13-or-15/21 EMAs, 200 EMA bias, a completed doji/trident candle wicking into the FVG midpoint, and a completed confirmation close before next-bar entry.

## Lookahead Controls

- FVGs are known only after the third 30-minute candle closes.
- The doji and confirmation candle are both completed before any signal is counted.
- EMA state uses only completed 30-minute closes through the confirmation candle.
- No future high, low, session range, VWAP, orderflow, or post-entry path is used.

## Duplicate Check

This was allowed to reach density screening because it is not the same edge as RTH FVG inversion, RTH EMA pullback with orderflow, fixed-time European-open drift, overnight range breakout, or measured-pivot continuation. It still failed before staged testing due to insufficient observations.

## Artifacts

- Density audit: `research_artifacts/nq_chartfanatics_london_trident_fvg_continuation_density_audit_20260630.md`
- Density CSV: `research_artifacts/nq_chartfanatics_london_trident_fvg_continuation_density_audit_20260630.csv`
- Summary CSV: `research_artifacts/nq_chartfanatics_london_trident_fvg_continuation_density_summary_20260630.csv`
- Backtest summary placeholder: `backtest-campaigns/nq_chartfanatics_london_trident_fvg_continuation/campaign_test_summary.json`

Final decision: FAIL.
