# Methodology Audit: nq_ofr_financial_stress_intraday

Date: 2026-06-22

Verdict: FAIL.

This campaign was a pre-PnL NQ port of `es_ofr_financial_stress_intraday`. It used a freshly generated NQ session feature file built from official OFR FSI data with the two-business-day availability lag.

## Pre-PnL Density Control

- The signal-density audit passed before any NQ PnL inspection: every declared stress-threshold row produced at least 64.173092 signals/year.
- The audit counted lagged OFR feature rows only; no stops, targets, fills, or PnL were evaluated.

## No-Lookahead Controls

- OFR observations are available only if dated on or before session_date minus two business days.
- Signals use the completed one-minute bar at the configured entry timestamp.
- No same-day unavailable OFR observation, final session high/low, final VWAP, future returns, or post-entry stress data is used.

## Execution Controls

- NQ tick size 0.25, point value 20.0, tick value 5.0.
- Commission 2.5 per contract and 1 tick slippage are configured.
- Same-bar stop/target conflicts use the engine pessimistic OHLC fill assumptions.
- All variants force same-day flatten and prohibit overnight exposure through config.

## Outcome

The campaign failed closed. High-credit reached WFA but had negative stitched OOS performance and early exit. There is no `candidate_strategy_report.md`.
