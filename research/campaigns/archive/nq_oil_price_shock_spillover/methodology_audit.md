# Methodology Audit: nq_oil_price_shock_spillover

Date: 2026-06-23

Verdict: FAIL.

This campaign was a pre-PnL NQ port of `es_oil_price_shock_spillover`. All five variants reused the ES parameter-space rescue mechanics and grids before any NQ PnL inspection. No NQ rescue was authorized or run after results.

## Pre-PnL Density Control

- Final density audit passed: `research_artifacts/nq_oil_price_shock_spillover_density_audit_20260623.md`.
- No density-only trim was needed.
- All declared entry-threshold corners had at least 50 full-history signals/year and at least 50 signals in the latest 252 sessions.

## No-Lookahead Controls

- A session dated D only uses the latest EIA WTI/Brent spot observation on or before D minus two business days.
- Rolling ranks are computed on lagged session features.
- Signals use completed one-minute bars and engine entry is next-bar-open or later.
- No final session high/low, final VWAP, future oil value, future return, or post-entry data is used for signal generation.

## Execution Controls

- NQ tick size 0.25, point value 20.0, tick value 5.0.
- Commission 2.5 per contract and 1 tick slippage are configured.
- Same-bar stop/target conflicts use pessimistic OHLC assumptions through the engine.
- All variants force same-day flatten and prohibit overnight exposure through config.

## Outcome

Four variants failed limited_core_grid_test. The only core-passing branch, wti_up_risk_off_short_1030, had 25/27 profitable core combinations and 1 benchmark-pass combination, but failed limited_monkey_test with profitable random-entry rate 0.235875 and median net profit -1537.5. No WFA, Monte Carlo, simulated incubation, or acceptance OOS stage was reached.

The WTI-up branch is not a candidate strategy because the monkey robustness gate failed after the core pass. No `candidate_strategy_report.md` was created.
