# ES Realized Volatility-of-Volatility Density Audit

Pre-performance density check only. Counts use lagged rolling-rank features, not trade PnL.

| variant | rank_column | threshold | signal_days | approx_trades_per_year |
|---|---|---:|---:|---:|
| high_1d_vov_premium_long_1000 | intraday_vov1_rank_252 | 0.25 | 1012 | 65.6 |
| high_1d_vov_premium_long_1000 | intraday_vov1_rank_252 | 0.35 | 1400 | 90.8 |
| high_1d_vov_premium_long_1000 | intraday_vov1_rank_252 | 0.45 | 1762 | 114.3 |
| high_1d_vov_stress_short_1030 | intraday_vov1_rank_252 | 0.25 | 1012 | 65.6 |
| high_1d_vov_stress_short_1030 | intraday_vov1_rank_252 | 0.35 | 1400 | 90.8 |
| high_1d_vov_stress_short_1030 | intraday_vov1_rank_252 | 0.45 | 1762 | 114.3 |
| low_1d_vov_calm_long_1130 | intraday_vov1_rank_252 | 0.25 | 905 | 58.7 |
| low_1d_vov_calm_long_1130 | intraday_vov1_rank_252 | 0.35 | 1288 | 83.5 |
| low_1d_vov_calm_long_1130 | intraday_vov1_rank_252 | 0.45 | 1625 | 105.4 |
| high_5d_vov_premium_long_1200 | intraday_vov5_rank_252 | 0.25 | 1080 | 70.0 |
| high_5d_vov_premium_long_1200 | intraday_vov5_rank_252 | 0.35 | 1451 | 94.1 |
| high_5d_vov_premium_long_1200 | intraday_vov5_rank_252 | 0.45 | 1811 | 117.4 |
| two_sided_20d_vov_state_1330 | intraday_vov20_rank_252 | 0.25 | 2008 | 130.2 |
| two_sided_20d_vov_state_1330 | intraday_vov20_rank_252 | 0.35 | 2654 | 172.1 |
| two_sided_20d_vov_state_1330 | intraday_vov20_rank_252 | 0.45 | 3395 | 220.2 |

Conclusion: all five variant shapes have plausible pre-test signal density above 50 trades/year across the declared threshold grid.
