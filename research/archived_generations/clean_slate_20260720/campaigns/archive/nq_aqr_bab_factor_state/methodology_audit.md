# Methodology Audit: nq_aqr_bab_factor_state

Date: 2026-06-22

Verdict: FAIL.

This campaign ported the ES AQR BAB factor-state edge to NQ using an NQ session-keyed feature file rebuilt with a 45-calendar-day AQR publication lag.

## No-Lookahead Controls

- Feature construction uses only AQR observations at least 45 calendar days old for each NQ session.
- Entry decisions are fixed-time intraday signals on completed one-minute bars, with next-bar-open execution by the engine.
- No current-session final NQ close, final range, final VWAP, post-entry data, or future AQR values are used.

## Execution Controls

- NQ tick size 0.25, point value 20.0, tick value 5.0.
- Commission 2.5 per contract and 1 tick slippage are configured.
- All variants flatten at 15:55 ET and prohibit overnight exposure.

## Outcome

All variants failed limited core grid stability; no candidate_strategy_report.md was created.
