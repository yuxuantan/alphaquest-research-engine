# NQ sector rotation risk-appetite density audit - 2026-06-22

Purpose: pre-PnL signal-density check for applying lagged sector ETF rotation states to NQ intraday exposure. Features use ETF closes available on or before one business day before each NQ session. No strategy PnL is inspected here.

Feature file: `data/external/nq_sector_rotation_features_20110103_20260612.csv`. Rows: 3813 from 2011-01-03 to 2026-06-12.

| variant | feature_column | operator | threshold | signals | signals_per_year | min_year_count | median_year_count | first_year | last_year |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cyclical_lead_long_1000 | cyclical_minus_defensive_1d_rank_252 | >= | 0.55 | 1732 | 112.19 | 53 | 109 | 2011 | 2026 |
| cyclical_lead_long_1000 | cyclical_minus_defensive_1d_rank_252 | >= | 0.6 | 1532 | 99.23 | 48 | 96.5 | 2011 | 2026 |
| cyclical_lead_long_1000 | cyclical_minus_defensive_1d_rank_252 | >= | 0.65 | 1360 | 88.09 | 43 | 86 | 2011 | 2026 |
| defensive_lead_short_1000 | cyclical_minus_defensive_1d_rank_252 | <= | 0.45 | 1711 | 110.83 | 48 | 111 | 2011 | 2026 |
| defensive_lead_short_1000 | cyclical_minus_defensive_1d_rank_252 | <= | 0.4 | 1514 | 98.06 | 45 | 97 | 2011 | 2026 |
| defensive_lead_short_1000 | cyclical_minus_defensive_1d_rank_252 | <= | 0.35 | 1344 | 87.05 | 38 | 85 | 2011 | 2026 |
| growth_lead_long_1030 | growth_minus_defensive_5d_rank_252 | >= | 0.55 | 1722 | 111.54 | 48 | 114.5 | 2011 | 2026 |
| growth_lead_long_1030 | growth_minus_defensive_5d_rank_252 | >= | 0.6 | 1522 | 98.58 | 43 | 100.5 | 2011 | 2026 |
| growth_lead_long_1030 | growth_minus_defensive_5d_rank_252 | >= | 0.65 | 1352 | 87.57 | 41 | 88.5 | 2011 | 2026 |
| defensive_rotation_short_1130 | cyclical_minus_defensive_5d_rank_252 | <= | 0.45 | 1736 | 112.44 | 55 | 109.5 | 2011 | 2026 |
| defensive_rotation_short_1130 | cyclical_minus_defensive_5d_rank_252 | <= | 0.4 | 1556 | 100.79 | 52 | 97 | 2011 | 2026 |
| defensive_rotation_short_1130 | cyclical_minus_defensive_5d_rank_252 | <= | 0.35 | 1358 | 87.96 | 44 | 83 | 2011 | 2026 |
| growth_acceleration_long_1330 | growth_minus_defensive_5d_rank_252 | >= | 0.6 | 1522 | 98.58 | 43 | 100.5 | 2011 | 2026 |
| growth_acceleration_long_1330 | growth_minus_defensive_5d_rank_252 | >= | 0.65 | 1352 | 87.57 | 41 | 88.5 | 2011 | 2026 |
| growth_acceleration_long_1330 | growth_minus_defensive_5d_rank_252 | >= | 0.7 | 1166 | 75.52 | 38 | 72 | 2011 | 2026 |

Decision: rank thresholds have sufficient raw session density for staged testing. Parameter grids are frozen before current NQ PnL evaluation.
