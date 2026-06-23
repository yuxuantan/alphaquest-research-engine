# Methodology Audit: nq_spx_0dte_trend_aligned_pressure

Date: 2026-06-22

Verdict: FAIL.

This campaign was a pre-PnL NQ port of `es_spx_0dte_trend_aligned_pressure`. It kept the five ES trend-aligned 0DTE mechanics and changed only NQ data, the NQ 0DTE calendar path, contract economics, and wording before testing.

## Pre-PnL Density Control

- Signal-density audit passed before any NQ PnL inspection: every declared entry-grid row produced at least 51.205928 signals/year over the full configured NQ RTH history.
- The audit used ex-ante SPX 0DTE calendar membership and completed NQ 30-minute and 120-minute trend windows only. No stops, targets, fills, or PnL were evaluated.

## No-Lookahead Controls

- Calendar membership is known before the session.
- Trend windows use only completed one-minute NQ bars ending at the configured signal timestamp.
- Signals from completed bars enter no earlier than the next bar open through the engine.
- No option volume, dealer position, final VWAP, future high/low, or post-signal path is used.

## Execution Controls

- NQ tick size 0.25, point value 20.0, tick value 5.0.
- Commission 2.5 per contract and 1 tick slippage are configured.
- Same-bar stop/target conflicts are handled by the engine under pessimistic OHLC assumptions.
- All variants force same-day flatten and prohibit overnight exposure through config.

## Outcome

The campaign failed closed. All five variants failed `limited_core_grid_test` with 0 profitable combinations. There is no `candidate_strategy_report.md`.
