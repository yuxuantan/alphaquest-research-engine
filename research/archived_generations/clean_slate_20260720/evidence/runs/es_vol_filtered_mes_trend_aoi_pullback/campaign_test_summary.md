# Campaign Test Summary: es_vol_filtered_mes_trend_aoi_pullback

Verdict: FAIL

All eight predeclared variants failed `limited_core_grid_test`. No variant reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

| variant_id | profitable | combos | benchmark passes | top net | top PF | top MAR | top TPY | top failure |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| lvn_trade15_vol_downshift_1500 | 32 | 81 | 0 | 485.00 | 2.169 | 3.876 | 26.3 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| prior_extreme_trade15_range10_1500 | 26 | 81 | 0 | 622.50 | 1.996 | 4.014 | 38.0 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| value_area_trade15_downside20_1500 | 24 | 81 | 0 | 715.00 | 2.032 | 5.585 | 32.7 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| overnight_trade15_downside20_1500 | 20 | 81 | 0 | 1045.00 | 2.148 | 8.210 | 44.1 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| market_trade15_absret5_1500 | 8 | 81 | 0 | 400.00 | 1.196 | 1.118 | 67.6 | preferred_min_total_trades;max_best_day_concentration |
| all_aoi_notional30_absret5_1500 | 6 | 81 | 1 | 870.00 | 1.229 | 2.800 | 123.5 | max_best_day_concentration |
| opening_trade15_range10_1200 | 2 | 81 | 0 | 92.50 | 1.109 | 0.481 | 24.5 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| profile_trade15_absorption_absret5_1500 | 0 | 81 | 0 | -147.50 | 0.825 | -0.627 | 21.3 | min_total_net_profit;min_trades_per_year;preferred_min_total_trades |
