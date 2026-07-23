# NQ Amihud Illiquidity Price Impact Density Audit - 2026-06-30

Pre-PnL audit only. The original ES threshold corner at `0.25` produced fewer than 50 signals/year for the NQ 5-day and 20-day high-illiquidity variants, so the NQ grid was widened before any NQ PnL inspection to `entry.params.illiq_rank_threshold = [0.30, 0.35, 0.45]`.

Data: `data/external/nq_amihud_illiquidity_features_20110103_20260612.csv` with 3,813 rows from 2011-01-03 through 2026-06-12. Minimum selected-grid density is 55.056304 signals/year.

| variant_id | rank_column | threshold | signals | signals_per_year |
| --- | --- | ---: | ---: | ---: |
| high_1d_illiq_premium_long_1000 | illiq1_rank_252 | 0.30 | 957 | 61.986921 |
| high_1d_illiq_premium_long_1000 | illiq1_rank_252 | 0.35 | 1130 | 73.192499 |
| high_1d_illiq_premium_long_1000 | illiq1_rank_252 | 0.45 | 1529 | 99.036576 |
| high_1d_illiq_stress_short_1030 | illiq1_rank_252 | 0.30 | 957 | 61.986921 |
| high_1d_illiq_stress_short_1030 | illiq1_rank_252 | 0.35 | 1130 | 73.192499 |
| high_1d_illiq_stress_short_1030 | illiq1_rank_252 | 0.45 | 1529 | 99.036576 |
| high_5d_illiq_premium_long_1130 | illiq5_rank_252 | 0.30 | 909 | 58.877860 |
| high_5d_illiq_premium_long_1130 | illiq5_rank_252 | 0.35 | 1060 | 68.658450 |
| high_5d_illiq_premium_long_1130 | illiq5_rank_252 | 0.45 | 1382 | 89.515074 |
| high_20d_illiq_premium_long_1200 | illiq20_rank_252 | 0.30 | 850 | 55.056304 |
| high_20d_illiq_premium_long_1200 | illiq20_rank_252 | 0.35 | 953 | 61.727833 |
| high_20d_illiq_premium_long_1200 | illiq20_rank_252 | 0.45 | 1216 | 78.762901 |
| two_sided_5d_illiq_state_1330 | illiq5_rank_252 | 0.30 | 2371 | 153.574703 |
| two_sided_5d_illiq_state_1330 | illiq5_rank_252 | 0.35 | 2735 | 177.151756 |
| two_sided_5d_illiq_state_1330 | illiq5_rank_252 | 0.45 | 3405 | 220.549078 |
