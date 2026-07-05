# NQ NAAIM Exposure Sentiment Density Audit - 2026-06-30

Pre-PnL audit only. NAAIM is a weekly survey, so expected signal density is near 52 sessions/year. All five fixed-entry variants clear the 50 signals/year floor, but only narrowly; no additional filters were introduced.

Data: `data/external/nq_naaim_exposure_features_20110103_20260612.csv` with 806 signal sessions from 2011-01-03 through 2026-06-12. Each NQ session uses the first RTH session at least two business days after the NAAIM observation date. Minimum selected-grid density is 52.206331 signals/year.

| variant_id | signals | signals_per_year |
| --- | ---: | ---: |
| level_median_contrarian_1000 | 806 | 52.206331 |
| level_rank_contrarian_1030 | 806 | 52.206331 |
| weekly_change_contrarian_1130 | 806 | 52.206331 |
| zscore_sign_contrarian_1200 | 806 | 52.206331 |
| ma_distance_contrarian_1400 | 806 | 52.206331 |
