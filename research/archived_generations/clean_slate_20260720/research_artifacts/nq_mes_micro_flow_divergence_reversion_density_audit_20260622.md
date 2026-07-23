# NQ MES Micro-Flow Divergence Density Audit

Date: 2026-06-22

Decision: FAIL.

This pre-PnL audit counts only configured entry-time signals from completed NQ/MES flow-divergence features. Stop and target grids are included in the CSV but do not affect density.

Sessions: 1760; years_252: 6.984127; rows audited: 180.

| variant | min_signals_per_year | max_signals_per_year | failing_combos |
| --- | ---: | ---: | ---: |
| afternoon_mes_large20_buy_pressure_short | 43.240909 | 45.818182 | 36 |
| afternoon_mes_large20_sell_pressure_long | 53.550000 | 57.988636 | 0 |
| midday_mes_price_richness_fade | 247.561364 | 247.561364 | 0 |
| morning_mes_buy_pressure_reversion_short | 21.334091 | 89.202273 | 18 |
| morning_mes_sell_pressure_reversion_long | 24.340909 | 98.509091 | 18 |

Min row: `morning_mes_buy_pressure_reversion_short` threshold=0.04 signals/year=21.334091.
Max row: `midday_mes_price_richness_fade` threshold=0.25 signals/year=247.561364.
