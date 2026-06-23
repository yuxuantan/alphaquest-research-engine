# Methodology Audit: nq_pivot_filtered_mes_participation_crowding_reversion

Date: 2026-06-22

Verdict: FAIL.

This campaign was a direct NQ port of `es_pivot_filtered_mes_participation_crowding_reversion`, selected before NQ PnL because the ES source family had strong core-grid profitability and failed later robustness rather than initial profitability.

## Pre-PnL Density Control

- Initial exact NQ signal-density audit failed only `morning_notional_down_reversal_long_window_1100`.
- Before any NQ PnL was inspected, that variant received one density-only share-rank relaxation from `[0.45, 0.55, 0.65]` to `[0.35, 0.40, 0.45]`; direction, session window, pivot filter, stops, targets, costs, and staged gates were unchanged.
- Final density audit passed every declared entry-grid corner with 55.195837 to 147.141962 signals per year.

## No-Lookahead Controls

- Entries use completed one-minute bars and next-bar-open execution.
- `return_column_prefix: nq` forces the base MES participation module to use NQ return tick columns.
- MES same-clock participation ranks are precomputed rank252 fields and treated as prior-history features.
- Multi-timeframe pivot structure confirms swing highs/lows only after the configured right-side confirmation bar is complete.
- No final session high/low, final VWAP, future orderflow, future returns, or unconfirmed future pivot is used for entry.

## Execution Controls

- NQ tick size 0.25, point value 20.0, tick value 5.0.
- Commission 2.5 per contract and 1 tick slippage are configured.
- Same-bar stop/target conflicts are handled by the engine under pessimistic OHLC assumptions.
- All variants force same-day flatten and prohibit overnight exposure through config.

## Outcome

The campaign failed closed. Only one variant cleared core stability, and that variant failed monkey robustness before WFA. There is no `candidate_strategy_report.md`.
