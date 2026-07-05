# NQ Gold Platinum Tail-Risk State Methodology Audit

Verdict: FAIL.

The campaign was rejected before staged PnL. The pre-PnL density audit found 30/45 declared entry-grid rows passed and only 2/5 variants passed all declared rows. High gold/platinum ratio variants had zero latest-252-session signals, while the low-ratio variant had zero early-window signals.

No PnL was inspected. No parameter rescue is authorized.

## Source And Edge

Primary source: Huang and Kilic (2019), "Gold, platinum, and expected stock returns", Journal of Financial Economics, DOI 10.1016/j.jfineco.2018.11.004.

Local expression: strict-prior daily gold/platinum futures ratio ranks select fixed-time NQ long/short exposure or require same-session NQ strength/weakness confirmation. The campaign tests only an intraday same-day expression of a lower-frequency expected-return state.

## Lookahead Controls

- Gold and platinum futures closes are joined with `allow_exact_matches=false`, so each NQ session uses only observations strictly before `session_date`.
- Entries can emit only after a completed five-minute RTH bar.
- Morning strength/weakness filters use only current-session bars completed up to the signal bar.
- No same-day metal close, future NQ session high/low, final VWAP, or post-entry path is used.

## Duplicate Check

This was allowed to reach density screening because it is not an equity-volatility, Treasury-volatility, oil, dollar, variance-risk-premium, or CBOE skew/tail-risk campaign. It is a precious-metals relative-value state based on gold versus platinum.

## Artifacts

- Density audit: `research_artifacts/nq_gold_platinum_tailrisk_state_density_audit_20260701.md`
- Density CSV: `research_artifacts/nq_gold_platinum_tailrisk_state_density_audit_20260701.csv`
- Summary CSV: `research_artifacts/nq_gold_platinum_tailrisk_state_density_summary_20260701.csv`
- Backtest summary placeholder: `backtest-campaigns/nq_gold_platinum_tailrisk_state/campaign_test_summary.json`
- Results CSV: `backtest-campaigns/nq_gold_platinum_tailrisk_state/campaign_results.csv`

Final decision: FAIL.
