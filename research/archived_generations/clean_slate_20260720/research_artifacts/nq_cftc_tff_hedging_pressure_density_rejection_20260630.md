# NQ CFTC TFF Hedging Pressure Density Rejection - 2026-06-30

Pre-PnL audit only. The ES `es_cftc_tff_hedging_pressure` edge was reviewed as a possible NQ transfer using `data/external/cftc_tff_hedging_pressure_features.csv`.

Decision: FAIL before staged PnL testing.

Reason: the corrected tradable feature window is 2013-04-15 through 2026-05-29. Within that window, the high/extreme positive and extreme negative source mechanics are below the 50 signals/year density floor. Widening those thresholds enough to clear density would collapse them into the broad positive/negative mechanics, creating duplicated variants inside the same edge.

| variant_id | operator | threshold | signals | signals_per_year |
| --- | --- | ---: | ---: | ---: |
| broad_negative_pressure_short_1100 | <= | -25000.0 | 1075 | 81.937343 |
| broad_negative_pressure_short_1100 | <= | -50000.0 | 669 | 50.991705 |
| broad_negative_pressure_short_1100 | <= | -100000.0 | 364 | 27.744366 |
| broad_positive_pressure_long_1100 | >= | 25000.0 | 909 | 69.284693 |
| broad_positive_pressure_long_1100 | >= | 47442.0 | 676 | 51.525250 |
| broad_positive_pressure_long_1100 | >= | 75000.0 | 413 | 31.479184 |
| extreme_negative_pressure_short_1330 | <= | -75000.0 | 472 | 35.976210 |
| extreme_negative_pressure_short_1330 | <= | -150000.0 | 248 | 18.902755 |
| extreme_negative_pressure_short_1330 | <= | -250000.0 | 154 | 11.738001 |
| extreme_positive_pressure_long_1330 | >= | 125000.0 | 275 | 20.960716 |
| extreme_positive_pressure_long_1330 | >= | 175000.0 | 260 | 19.817404 |
| extreme_positive_pressure_long_1330 | >= | 250000.0 | 226 | 17.225897 |
| high_positive_pressure_long_0935 | >= | 75000.0 | 413 | 31.479184 |
| high_positive_pressure_long_0935 | >= | 98748.0 | 339 | 25.838846 |
| high_positive_pressure_long_0935 | >= | 150000.0 | 265 | 20.198508 |
