# Methodology Audit: nq_trend_filtered_mes_participation_crowding

Date: 2026-06-22

Verdict: FAIL.

This campaign was a direct NQ port of `es_trend_filtered_mes_participation_crowding`, selected before NQ PnL because the ES source family had reached WFA OOS Monte Carlo after a 100% profitable core grid.

## No-Lookahead Controls

- Entries use completed one-minute bars and next-bar-open execution.
- `return_column_prefix: nq` forces the pullback return filter to use NQ return tick columns.
- MES same-clock participation ranks are precomputed rank252 fields and treated as prior-history features.
- The trend window ends before the pullback/crowding window begins.
- No final VWAP, final session range, future orderflow, future returns, or post-entry data is used for entry.

## Execution Controls

- NQ tick size 0.25, point value 20.0, tick value 5.0.
- Commission 2.5 per contract and 1 tick slippage are configured.
- Same-bar stop/target conflicts are handled by the engine under pessimistic OHLC assumptions.
- All variants force same-day flatten and prohibit overnight exposure through config.

## Outcome

The campaign failed closed. The only variant that cleared core stability failed monkey robustness before WFA, so there is no candidate_strategy_report.md.
