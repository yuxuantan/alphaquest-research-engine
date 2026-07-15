# Methodology Audit: nq_mes_micro_flow_divergence_reversion

Date: 2026-06-22

Verdict: FAIL.

This campaign was a direct NQ port of `es_mes_micro_flow_divergence_reversion`, selected before NQ PnL because the ES source family had variants that passed core and sometimes monkey gates before failing later validation.

## Pre-PnL Density And Loader Controls

- Initial NQ signal-density audit failed selected morning and afternoon thresholds before any NQ PnL was inspected.
- A density-only pre-PnL reform relaxed the affected `flow_threshold` grids; entry modules, flow columns, directions, signal times, stop/target grids, costs, sessions, and validation gates were unchanged.
- Final density audit passed all declared entry-grid corners with 50.4 to 247.561364 signals per year across 1760 RTH sessions.
- `run1` halted before testing because `data.feature_set: nq_mes_completed_flow_divergence` was descriptive but unsupported. The pre-PnL loader fix set `data.feature_set: none`; all reported results use clean `run2` only.

## No-Lookahead Controls

- Entries use completed one-minute bars and next-bar-open execution.
- Flow-divergence features are rolling same-session NQ/MES windows using only current and prior completed bars.
- NQ/MES bars are aligned by timestamp in America/New_York RTH data.
- Signal timestamps are fixed in config and do not use future session high/low, final VWAP, future returns, or post-entry flow.

## Execution Controls

- NQ tick size 0.25, point value 20.0, tick value 5.0.
- Commission 2.5 per contract and 1 tick slippage are configured.
- Same-bar stop/target conflicts are handled by the engine under pessimistic OHLC assumptions.
- All variants force same-day flatten and prohibit overnight exposure through config.

## Outcome

The campaign failed closed. Two variants failed `limited_core_grid_test`; three variants passed core but failed `limited_monkey_test` before WFA. There is no `candidate_strategy_report.md`.
