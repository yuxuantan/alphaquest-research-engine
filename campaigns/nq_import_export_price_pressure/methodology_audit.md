# Methodology Audit: nq_import_export_price_pressure

Date: 2026-06-23

Verdict: FAIL.

This campaign was a pre-PnL NQ port of `es_import_export_price_pressure`, starting from the existing ES stop-distance rescue configs because that was the strongest prior ES evidence in the family.

## Pre-PnL Density Control

- Initial direct NQ port failed density before any NQ PnL: `research_artifacts/nq_import_export_price_pressure_initial_density_rejected_20260623.md`.
- Density-only reform removed the strict 2 bps completed-return row and broadened only underpowered macro-rank cutoffs while preserving setup mode, signal time, flow column, stop grid, target grid, data, costs, sessions, and gates.
- Post-reform audit passed: worst full-history density 50.294256 signals/year, worst latest-252 density 55.0 signals/year.

## No-Lookahead Controls

- A session only uses the latest monthly import/export observation whose conservative observation-date-plus-51-calendar-day availability date is on or before the NQ session date.
- Rolling ranks are computed on monthly data through the mapped available observation.
- Signals use completed NQ one-minute bars and cumulative orderflow only through the completed signal bar; engine entry is next-bar-open or later.
- No final session high/low, final VWAP, future monthly data revision, or post-entry path is used for the signal.

## Execution Controls

- NQ tick size 0.25, point value 20.0, tick value 5.0.
- Commission 2.5 per contract and 1 tick slippage are configured.
- Same-bar stop/target conflicts use pessimistic OHLC assumptions through the engine.
- All variants force same-day flatten and prohibit overnight exposure through config.

## Outcome

The campaign failed closed. Four variants failed limited core; the only core survivor failed monkey drawdown robustness. There is no `candidate_strategy_report.md`.
