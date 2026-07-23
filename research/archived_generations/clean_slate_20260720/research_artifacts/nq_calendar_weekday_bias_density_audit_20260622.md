# NQ Calendar Weekday Bias Density Audit

Generated on 2026-06-22 before any NQ PnL testing for `nq_calendar_weekday_bias`.

Input: NQ RTH session dates from `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`.

Availability rule: session weekday is known before the session starts and contains no price-derived information.

| Variant | Weekday directions | Signals | Signals/year |
|---|---|---:|---:|
| mon_fri_weekend_reversal_1000 | Monday short; Friday long | 1470 | 95.22 |
| tue_wed_midweek_strength_1000 | Tuesday long; Wednesday long | 1573 | 101.89 |
| thu_fri_lateweek_strength_1030 | Thursday long; Friday long | 1531 | 99.17 |
| mon_tue_turnaround_1000 | Monday short; Tuesday long | 1496 | 96.90 |
| wed_thu_midweek_fade_1130 | Wednesday short; Thursday short | 1556 | 100.79 |

Decision: approve for authoring. Weekday mappings are predeclared from the calendar-anomaly family and signal density only; no PnL or intraday outcome data was inspected during this screen.
