# Methodology Audit: nq_usdjpy_safe_haven_spillover

Date: 2026-06-22

Verdict: FAIL.

This campaign was a pre-PnL NQ port of `es_usdjpy_safe_haven_spillover`. It used a freshly generated NQ session feature file built from local FRED DEXJPUS data with a one-business-day availability lag.

## Pre-PnL Density Control

- The signal-density audit passed before any NQ PnL inspection: every declared USDJPY threshold row produced at least 53.466562 signals/year.
- The audit counted lagged USDJPY feature rows only; no stops, targets, fills, or PnL were evaluated.

## No-Lookahead Controls

- Signals never use same-date USDJPY observations.
- Rolling ranks are computed after applying the one-business-day availability lag to NQ session dates.
- Signals use completed one-minute NQ bars and enter at next bar open or later through the engine.
- No final session high/low, final VWAP, future FX observation, or post-entry path is used.

## Execution Controls

- NQ tick size 0.25, point value 20.0, tick value 5.0.
- Commission 2.5 per contract and 1 tick slippage are configured.
- Same-bar stop/target conflicts use pessimistic OHLC assumptions.
- All variants force same-day flatten and prohibit overnight exposure through config.

## Outcome

The campaign failed closed. Strong-yen reached WFA but failed out-of-sample and early-exited; weak-yen failed monkey; the remaining variants failed core. There is no `candidate_strategy_report.md`.
