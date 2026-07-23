# ES Turn-of-Month Orderflow Confirmation Density Gate - 2026-06-20

Decision: FAIL before campaign authoring.

## Scope

This is a pre-PnL eligibility screen for a possible bounded composite:
turn-of-month seasonality as the primary edge, with completed first-30-minute
ES aggregate orderflow and price confirmation as the secondary condition.

No PnL, stop/target outcome, equity curve, core-grid result, monkey result, WFA
result, or Monte Carlo result was inspected. No campaign was authored.

## Duplicate And Mechanics Review

The active `es_turn_of_month_seasonality` campaign already tested the pure
calendar edge and failed all original and one-time rescue variants before WFA.
A new composite would only be eligible if the orderflow confirmation created a
convincing, predeclared mechanism without stretching the calendar window into a
generic half-month filter.

The intended signal was a maximum of one long ES trade per qualifying session:
use only completed RTH bars from 09:30 through 09:59 ET, decide at 10:00 ET,
then rely on the engine for next-bar execution. The orderflow confirmation was
positive completed first-30-minute signed imbalance, optionally requiring a
small positive opening return.

## Data And Timing

- Source: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`.
- Full screen period: 2011-01-03 through 2026-06-09, 3,817 RTH sessions, 15.43 years.
- Limited-core benchmark window checked: 2011-02-22 through 2012-09-06, 374 RTH sessions, 1.54 years.
- Signal inputs: completed 09:30-09:59 ET RTH bars only.
- No latest holdout data was used for tuning; this was an opportunity-count screen only.

## Density Results

| Window definition | Confirmation | Full signals/year | Limited-core signals/year | Decision |
|---|---:|---:|---:|---|
| Calendar first/last 4 days | return >= 0 ticks, signed imbalance >= 0 | 22.81 | 25.35 | Fail density |
| Calendar first/last 4 days | return >= 2 ticks, signed imbalance >= 0.01 | 17.95 | 23.40 | Fail density |
| Calendar first/last 5 days | return >= 0 ticks, signed imbalance >= 0 | 29.42 | 32.50 | Fail density |
| Calendar first/last 5 days | return >= 2 ticks, signed imbalance >= 0.01 | 23.52 | 29.90 | Fail density |
| Trading first 3 / last 1 days | return >= 0 ticks, signed imbalance >= 0 | 16.98 | 18.20 | Fail density |
| Trading first 3 / last 1 days | return >= 2 ticks, signed imbalance >= 0.01 | 14.00 | 17.55 | Fail density |
| Trading first/last 4 days | return >= 0 ticks, signed imbalance >= 0 | 35.51 | 40.94 | Fail density |
| Trading first/last 4 days | return >= 2 ticks, signed imbalance >= 0.01 | 28.32 | 35.75 | Fail density |
| Calendar first/last 7 days | return >= 0 ticks, signed imbalance >= 0 | 41.48 | 44.19 | Fail density |
| Trading first/last 6 days | return >= 0 ticks, signed imbalance >= 0 | 54.37 | 56.54 | Reject as overbroad |
| Trading first/last 7 days | return >= 2 ticks, signed imbalance >= 0.01 | 50.81 | 55.89 | Reject as overbroad |

## Conclusion

Faithful turn-of-month windows fail the 50 trades/year feasibility screen once
any completed orderflow confirmation is added. The only windows that clear the
density threshold use the first and last 6-7 trading days of every month, which
can cover more than half of many months. That is no longer a convincing
turn-of-month edge and would be too broad to justify as a new non-duplicate
campaign after the pure turn-of-month campaign failed.

Final decision: FAIL. Do not author `es_turn_of_month_orderflow_confirmation`
under the current methodology.
