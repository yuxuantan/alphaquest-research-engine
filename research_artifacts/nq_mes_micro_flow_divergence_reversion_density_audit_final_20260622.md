# NQ MES Micro-Flow Divergence Final Density Audit

Date: 2026-06-22

Decision: PASS.

This final pre-PnL audit follows density-only threshold reformulation. It counts configured entry-time signals from completed NQ/MES flow-divergence features only; no post-entry returns or PnL are inspected.

| variant | min_signals_per_year | max_signals_per_year | failing_combos |
| --- | ---: | ---: | ---: |
| afternoon_mes_large20_buy_pressure_short | 50.400000 | 51.688636 | 0 |
| afternoon_mes_large20_sell_pressure_long | 53.550000 | 57.988636 | 0 |
| midday_mes_price_richness_fade | 247.561364 | 247.561364 | 0 |
| morning_mes_buy_pressure_reversion_short | 61.281818 | 102.661364 | 0 |
| morning_mes_sell_pressure_reversion_long | 67.152273 | 117.265909 | 0 |

Min row: `afternoon_mes_large20_buy_pressure_short` threshold=0.03 signals/year=50.400000.
Max row: `midday_mes_price_richness_fade` threshold=0.25 signals/year=247.561364.
