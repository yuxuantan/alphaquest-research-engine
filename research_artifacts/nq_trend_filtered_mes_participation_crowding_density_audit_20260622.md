# nq_trend_filtered_mes_participation_crowding Pre-PnL Density Audit

Date: 2026-06-22

This audit counts only completed-bar signal eligibility for the declared NQ port before any NQ PnL was inspected.
Data: `data/cache/orderflow/nq_mes_participation_crowding_1m_20190506_20260612_full_rth_ny.csv`.
Window: 2019-05-06 through 2026-06-12; elapsed calendar years: 7.1020.

Decision: PASS. Every declared entry-grid corner is above the 50 signals/year pre-PnL density floor.

## Variant Summary

| variant_id | min | max | mean |
| --- | --- | --- | --- |
| afternoon_notional_trend_pullback_reversal_1400 | 53.787779 | 75.471858 | 64.864495 |
| early_afternoon_notional_trend_pullback_reversal_1300 | 58.997591 | 78.428778 | 68.838345 |
| midday_notional_trend_pullback_reversal_1200 | 58.152756 | 76.457498 | 67.289482 |
| morning_notional_trend_pullback_reversal_1030 | 59.983231 | 80.118446 | 70.887850 |
| morning_trade_trend_pullback_reversal_1030 | 60.546453 | 80.400058 | 70.981721 |

## Controls

- Signal timestamps use fixed completed 1-minute bar closes.
- The NQ return column is used through `return_column_prefix: nq`.
- MES participation ranks are same-clock rank252 fields already shifted to prior same-clock history in the cache.
- The trend window ends before the pullback/crowding window starts.
- This audit does not inspect net profit, trade outcomes, equity curves, or selected best parameters.
