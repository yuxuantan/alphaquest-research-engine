# nq_pivot_filtered_mes_participation_crowding_reversion Pre-PnL Density Audit

Date: 2026-06-22

This audit feeds the actual `market_structure_filtered_entry` wrapper over `data/cache/orderflow/nq_mes_participation_crowding_1m_20190506_20260612_full_rth_ny.csv` before any NQ PnL is inspected.
Window: 2019-05-06 through 2026-06-12; elapsed calendar years: 7.1020.

Decision: FAIL.

## Variant Summary

| variant_id | min | max | mean |
| --- | --- | --- | --- |
| afternoon_trade_two_sided_reversal_window_1500 | 77.583944 | 104.337028 | 91.758385 |
| late_morning_trade_two_sided_reversal_window_1200 | 73.359773 | 101.239302 | 87.987921 |
| midday_notional_two_sided_reversal_window_1330 | 108.561199 | 147.141962 | 127.867226 |
| morning_notional_down_reversal_long_window_1100 | 40.129626 | 55.336642 | 47.686199 |
| morning_notional_two_sided_reversal_window_1130 | 89.83404 | 119.68485 | 104.822025 |

## Controls

- Counts use the actual completed multi-timeframe pivot wrapper.
- The base MES participation module uses `return_column_prefix: nq`.
- Each session is capped at one accepted signal to match `max_trades_per_day: 1`.
- Stops, targets, trade PnL, equity curves, and selected best parameters are not inspected.

Total runtime seconds: 613.1
