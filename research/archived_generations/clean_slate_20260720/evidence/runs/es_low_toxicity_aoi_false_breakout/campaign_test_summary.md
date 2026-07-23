# Campaign Test Summary: es_low_toxicity_aoi_false_breakout

Verdict: FAIL

All eight predeclared variants failed `limited_core_grid_test`. No variant reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

| variant_id | profitable | combos | benchmark passes | top net | top PF | top MAR | top TPY | top failure |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| market_aoi_largequiet_1500 | 37 | 81 | 0 | 442.50 | 4.612 | 8.341 | 9.2 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| lvn_largequiet_1500 | 36 | 81 | 0 | 470.00 | 0.000 | 0.000 | 365.2 | preferred_min_total_trades;max_best_day_concentration |
| overnight_signedquiet_1500 | 4 | 81 | 0 | 1740.00 | 1.165 | 0.715 | 80.7 | max_consecutive_losses;max_best_day_concentration |
| value_area_signedquiet_1500 | 2 | 81 | 0 | 505.00 | 1.204 | 0.401 | 16.3 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| poc_signedquiet_1500 | 0 | 81 | 0 | -660.00 | 0.766 | -0.386 | 21.4 | min_total_net_profit;min_trades_per_year;max_consecutive_losses;preferred_min_total_trades |
| opening_aoi_signedquiet_1200 | 0 | 81 | 0 | -1820.00 | 0.479 | -0.816 | 31.8 | min_total_net_profit;min_trades_per_year;preferred_min_total_trades |
| market_aoi_signedquiet_1500 | 0 | 81 | 0 | -3885.00 | 0.624 | -0.608 | 60.5 | min_total_net_profit;max_consecutive_losses |
| all_aoi_signedquiet_1500 | 0 | 81 | 0 | -5775.00 | 0.509 | -0.634 | 71.7 | min_total_net_profit |
