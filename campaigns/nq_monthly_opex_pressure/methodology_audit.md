# Methodology Audit: nq_monthly_opex_pressure

Date: 2026-06-23

Verdict: FAIL.

This campaign was a pre-PnL NQ port of `es_monthly_opex_pressure`. The Thursday positioning short used the strongest ES stop-distance rescue source; the post-OPEX Monday long used the ES minimum-RR source; the other variants used ES parameter-space rescue sources. No NQ rescue was authorized or run after results.

## Event-Density Control

- Event-density audit: `research_artifacts/nq_monthly_opex_pressure_event_density_audit_20260623.md`.
- Monthly OPEX is a low-frequency calendar-event strategy: roughly 8 non-quarterly events/year per signal type.
- The generic 50-signals/year screen was not used as a rejection rule; low-frequency risk was left to core benchmarks, WFA selection, and robustness gates.

## No-Lookahead Controls

- The monthly OPEX calendar is deterministic and known before the session.
- Signals trigger only on predeclared previous, OPEX, or next regular-session dates.
- Signals use completed one-minute bars and engine entry is next-bar-open or later.
- No final session high/low, final VWAP, future return, or post-entry path information is used for signal generation.

## Execution Controls

- NQ tick size 0.25, point value 20.0, tick value 5.0.
- Commission 2.5 per contract and 1 tick slippage are configured.
- Same-bar stop/target conflicts use pessimistic OHLC assumptions through the engine.
- All variants force same-day flatten and prohibit overnight exposure through config.

## Outcome

Four variants failed limited_core_grid_test or did not meet benchmark concentration requirements. The only core-and-monkey passing branch, nonquarterly_opex_thursday_positioning_short_1330, failed walk_forward_analysis: first training window had no selectable row and stitched OOS trades were 0. No Monte Carlo, simulated incubation, or acceptance OOS stage was reached.

The Thursday branch is not a candidate strategy because WFA produced no stitched OOS evidence. No `candidate_strategy_report.md` was created.
