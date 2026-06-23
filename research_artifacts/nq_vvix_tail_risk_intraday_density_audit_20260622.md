# NQ VVIX Tail Risk Density Audit - 2026-06-22

This audit uses only pre-PnL Cboe VVIX/VIX feature ranks from `data/external/nq_vvix_tail_risk_features_20110103_20260612.csv`. It checks planned ES-derived NQ port thresholds before any NQ backtest results are inspected.

| variant | driver_column | operator | threshold | valid_sessions | signal_sessions | signal_rate | annualized_signals | min_year_signals | max_year_signals | active_years |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| high_vvix_short_1000 | vvix_close_rank_252 | >= | 0.65 | 3754 | 1482 | 0.3948 | 99.48 | 32 | 156 | 16 |
| high_vvix_short_1000 | vvix_close_rank_252 | >= | 0.7 | 3754 | 1290 | 0.3436 | 86.6 | 26 | 133 | 16 |
| high_vvix_short_1000 | vvix_close_rank_252 | >= | 0.75 | 3754 | 1079 | 0.2874 | 72.43 | 22 | 106 | 16 |
| low_vvix_long_1030 | vvix_close_rank_252 | <= | 0.5 | 3754 | 1774 | 0.4726 | 119.09 | 24 | 195 | 16 |
| low_vvix_long_1030 | vvix_close_rank_252 | <= | 0.45 | 3754 | 1602 | 0.4267 | 107.54 | 21 | 185 | 16 |
| low_vvix_long_1030 | vvix_close_rank_252 | <= | 0.4 | 3754 | 1454 | 0.3873 | 97.6 | 19 | 178 | 16 |
| rising_vvix_short_1130 | vvix_change_1d_rank_252 | >= | 0.65 | 3753 | 1339 | 0.3568 | 89.91 | 41 | 93 | 16 |
| rising_vvix_short_1130 | vvix_change_1d_rank_252 | >= | 0.7 | 3753 | 1147 | 0.3056 | 77.02 | 34 | 85 | 16 |
| rising_vvix_short_1130 | vvix_change_1d_rank_252 | >= | 0.75 | 3753 | 965 | 0.2571 | 64.8 | 30 | 74 | 16 |
| falling_vvix_long_1200 | vvix_change_1d_rank_252 | <= | 0.4 | 3753 | 1482 | 0.3949 | 99.51 | 50 | 112 | 16 |
| falling_vvix_long_1200 | vvix_change_1d_rank_252 | <= | 0.35 | 3753 | 1310 | 0.3491 | 87.96 | 38 | 104 | 16 |
| falling_vvix_long_1200 | vvix_change_1d_rank_252 | <= | 0.3 | 3753 | 1115 | 0.2971 | 74.87 | 34 | 88 | 16 |
| high_vvix_vix_ratio_short_1330 | vvix_vix_ratio_rank_252 | >= | 0.6 | 3754 | 1720 | 0.4582 | 115.46 | 8 | 230 | 16 |
| high_vvix_vix_ratio_short_1330 | vvix_vix_ratio_rank_252 | >= | 0.65 | 3754 | 1583 | 0.4217 | 106.26 | 3 | 214 | 16 |
| high_vvix_vix_ratio_short_1330 | vvix_vix_ratio_rank_252 | >= | 0.7 | 3754 | 1415 | 0.3769 | 94.99 | 3 | 203 | 16 |
