# Methodology Audit: nq_sector_dispersion_state

Date: 2026-06-23

Verdict: FAIL.

This campaign was a pre-PnL NQ port of `es_sector_dispersion_state`. The rising 1-day dispersion short variant used the strongest ES stop-distance rescue config; the other four variants used ES parameter-space rescue configs. No NQ PnL was inspected before authoring the campaign or before the density-only grid trim.

## Pre-PnL Density Control

- Initial direct NQ port required density-only reform: `research_artifacts/nq_sector_dispersion_state_initial_density_rejected_20260623.md`.
- The reform removed `rank_max=0.25` from `low_1d_dispersion_long_1200` before any NQ PnL inspection because its latest-252 signal count was below 50.
- Final density audit passed: `research_artifacts/nq_sector_dispersion_state_density_audit_20260623.md`.

## No-Lookahead Controls

- A session dated D only uses sector ETF adjusted closes on or before D minus one business day.
- Signals use completed one-minute bars and engine entry is next-bar-open or later.
- No same-day ETF close, final session high/low, final VWAP, future sector return, or post-entry path is used for signal generation.

## Execution Controls

- NQ tick size 0.25, point value 20.0, tick value 5.0.
- Commission 2.5 per contract and 1 tick slippage are configured.
- Same-bar stop/target conflicts use pessimistic OHLC assumptions through the engine.
- All variants force same-day flatten and prohibit overnight exposure through config.

## Outcome

All five variants failed `limited_core_grid_test`. `rising_1d_dispersion_short_1130` had 17/27 profitable combinations and 13 benchmark-pass combinations, but 0.6296 profitable rate is below the required 0.70 gate. No rescue was run after NQ results, and no `candidate_strategy_report.md` was created.
