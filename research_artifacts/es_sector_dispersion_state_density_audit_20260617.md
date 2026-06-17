# ES sector dispersion state density audit - 2026-06-17

Decision: eligible for staged testing.

This campaign uses `data/external/es_sector_dispersion_features_20110103_20260609.csv`, built from local ES session dates and the existing no-cost Yahoo sector ETF cache. No paid data was downloaded.

Feature availability rule: an ES session dated D can only use sector ETF adjusted closes with observation date on or before D minus one business day. The entry module waits for a completed ES RTH bar and therefore relies on next-bar execution.

Feature file coverage:

| rows | date range | valid rank rows |
| ---: | --- | ---: |
| 3817 | 2011-01-03 to 2026-06-09 | 3817 |

Proposed original variants:

| variant | driver | threshold grid | strictest signal count | strictest signals/year |
| --- | --- | --- | ---: | ---: |
| high_1d_dispersion_short_1000 | sector_dispersion_1d_rank_252 >= threshold | 0.55, 0.60, 0.65 | 1402 | 90.9 |
| high_5d_dispersion_short_1030 | sector_dispersion_5d_rank_252 >= threshold | 0.55, 0.60, 0.65 | 1393 | 90.3 |
| rising_1d_dispersion_short_1130 | sector_dispersion_change_1d_rank_252 >= threshold | 0.55, 0.60, 0.65 | 1357 | 87.9 |
| low_1d_dispersion_long_1200 | sector_dispersion_1d_rank_252 <= threshold | 0.45, 0.40, 0.35 | 1295 | 83.9 |
| falling_5d_dispersion_long_1330 | sector_dispersion_change_5d_rank_252 <= threshold | 0.45, 0.40, 0.35 | 1330 | 86.2 |

All five variants remain comfortably above the 50 trades/year feasibility floor at the strictest original threshold. Proceed to preflight and staged testing without changing mechanics after results are seen.
