# Campaign Test Summary: es_mes_crowding_aoi_trap_reversion

Verdict: FAIL

All eight predeclared MES-crowding AOI trap-reversion variants failed limited_core_grid_test. No variant reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

## Best Limited-Core Variant

- Variant: `all_aoi_notional30_delta_1500`
- Profitable iterations: 35/81
- Benchmark-passing combinations: 1
- Top net profit: 2465.0
- Top profit factor: 1.3677732189481537
- Top MAR: 5.508196271079035
- Top trades/year: 175.39355213476617
- Top max drawdown: 1297.5
- Top failure reason: 

## Variant Results

| variant | profitable | benchmark | top_net | top_pf | top_mar | top_tpy | failure |
|---|---:|---:|---:|---:|---:|---:|---|
| all_aoi_notional30_delta_1500 | 35/81 | 1 | 2465.0 | 1.3677732189481537 | 5.508196271079035 | 175.39355213476617 |  |
| overnight_trade15_delta_1500 | 48/81 | 0 | 1530.0 | 1.9272727272727272 | 6.294629765815146 | 70.073498390141 | preferred_min_total_trades;max_best_day_concentration |
| prior_extreme_trade15_delta_1500 | 24/81 | 0 | 1112.5 | 1.6303116147308783 | 6.4906397982372885 | 75.02032549316064 | preferred_min_total_trades |
| lvn_trade15_delta_1500 | 23/81 | 0 | 1007.5 | 1.5387700534759359 | 5.874962596786153 | 77.52100300959934 | max_best_day_concentration |
| value_area_trade15_delta_1500 | 29/81 | 0 | 710.0 | 1.3741765480895916 | 2.0990627638659967 | 69.62668784749802 | preferred_min_total_trades;max_best_day_concentration |
| profile_aoi_trade15_absorption_1500 | 2/81 | 0 | 320.0 | 1.217687074829932 | 0.8939874459240763 | 43.59702837959654 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| market_aoi_trade15_delta_1500 | 0/81 | 0 | -90.0 | 0.9768190598840953 | -0.23162028095138412 | 140.22054193192525 | min_total_net_profit |
| opening_range_trade15_delta_1200 | 0/81 | 0 | -245.0 | 0.9436457734330075 | -0.5971505807755279 | 131.53429215960477 | min_total_net_profit |
