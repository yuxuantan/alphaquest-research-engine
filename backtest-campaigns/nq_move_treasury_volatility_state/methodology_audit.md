# NQ MOVE Treasury Implied Volatility State Methodology Audit

Verdict: FAIL.

The campaign was rejected before staged PnL. The pre-PnL density audit found 43/45 declared entry-grid rows passed, but only 3/5 variants passed all declared rows. The two high-MOVE short variants failed because the strictest high-MOVE/rising-MOVE threshold produced only 4 signals in the latest 252 sessions.

No PnL was inspected. No parameter rescue is authorized.

## Source And Edge

Primary sources: BIS Working Paper 606; Pan and Chan (2018), "A new government bond volatility index predictor for the U.S. equity premium"; ICE BofA MOVE Index daily history via Yahoo Finance.

Local expression: prior daily MOVE close, one-day change, and five-day change ranks are joined strictly before each NQ session. Five fixed-time variants test risk-off shorts under high/rising MOVE, risk-on longs under low/falling or crushed MOVE, and same-session NQ confirmation for spike/crush variants.

## Lookahead Controls

- MOVE observations are joined with `allow_exact_matches=false`, so an NQ session uses only the latest MOVE close strictly before `session_date`.
- Entries can emit only after a completed five-minute RTH bar.
- Morning strength/weakness filters use only current-session bars completed up to the signal bar.
- No same-day MOVE close, future NQ session high/low, final VWAP, or post-entry path is used.

## Duplicate Check

This was allowed to reach density screening because it is not a Treasury yield-level, real-yield, breakeven, equity VIX, VVIX, VIX term-structure, or Treasury-rate/orderflow campaign. It tests Treasury implied volatility as a distinct cross-asset risk-state channel.

## Artifacts

- Density audit: `research_artifacts/nq_move_treasury_volatility_state_density_audit_20260701.md`
- Density CSV: `research_artifacts/nq_move_treasury_volatility_state_density_audit_20260701.csv`
- Summary CSV: `research_artifacts/nq_move_treasury_volatility_state_density_summary_20260701.csv`
- Backtest summary placeholder: `backtest-campaigns/nq_move_treasury_volatility_state/campaign_test_summary.json`
- Results CSV: `backtest-campaigns/nq_move_treasury_volatility_state/campaign_results.csv`

Final decision: FAIL.
