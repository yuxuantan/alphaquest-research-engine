# NQ Dollar Risk-Appetite Intraday Density Audit - 2026-06-30

Pre-PnL audit only. The declared ES dollar-risk grids were checked against the NQ RTH session cache before any NQ PnL inspection. No density adjustment was needed.

Data: `data/external/nq_dollar_risk_appetite_features_20110103_20260612.csv` with 3,813 rows from 2011-01-03 through 2026-06-12. Dollar observations use the latest FRED DTWEXBGS observation on or before session date minus one business day. Minimum selected-grid density is 53.242685 signals/year.

| variant_id | threshold | mode | signals | signals_per_year |
| --- | ---: | --- | ---: | ---: |
| dollar_up_risk_off_short_1000 | 0.55 | min | 1714 | 111.019418 |
| dollar_up_risk_off_short_1000 | 0.60 | min | 1523 | 98.647943 |
| dollar_up_risk_off_short_1000 | 0.65 | min | 1333 | 86.341240 |
| dollar_down_risk_on_long_1030 | 0.45 | max | 1661 | 107.586496 |
| dollar_down_risk_on_long_1030 | 0.40 | max | 1462 | 94.696843 |
| dollar_down_risk_on_long_1030 | 0.35 | max | 1261 | 81.677647 |
| high_dollar_up_short_1130 | 0.55 | min2 | 1141 | 73.904992 |
| high_dollar_up_short_1130 | 0.60 | min2 | 981 | 63.541452 |
| high_dollar_up_short_1130 | 0.65 | min2 | 822 | 53.242685 |
| five_day_dollar_up_short_1200 | 0.55 | min | 1725 | 111.731912 |
| five_day_dollar_up_short_1200 | 0.60 | min | 1546 | 100.137702 |
| five_day_dollar_up_short_1200 | 0.65 | min | 1343 | 86.988961 |
| five_day_dollar_down_long_1330 | 0.45 | max | 1647 | 106.679686 |
| five_day_dollar_down_long_1330 | 0.40 | max | 1432 | 92.753680 |
| five_day_dollar_down_long_1330 | 0.35 | max | 1274 | 82.519684 |
