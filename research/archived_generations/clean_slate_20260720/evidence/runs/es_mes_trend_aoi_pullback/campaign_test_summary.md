# Campaign Test Summary: es_mes_trend_aoi_pullback

Verdict: FAIL

All five predeclared trend-aligned MES-crowding AOI pullback variants failed limited_core_grid_test. No variant reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

## Best Limited-Core Variant

- Variant: `overnight_trade15_trend_pullback_1500`
- Profitable iterations: 20/81
- Benchmark-passing combinations: 0
- Top net profit: 1045.0
- Top profit factor: 2.1483516483516483
- Top MAR: 8.209668091705726
- Top trades/year: 44.13728915708608
- Top max drawdown: 520.0
- Top failure reason: min_trades_per_year;preferred_min_total_trades;max_best_day_concentration

## Variant Results

| variant | profitable | benchmark | top_net | top_pf | top_mar | top_tpy | failure |
|---|---:|---:|---:|---:|---:|---:|---|
| overnight_trade15_trend_pullback_1500 | 20/81 | 0 | 1045.0 | 2.1483516483516483 | 8.209668091705726 | 44.13728915708608 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| all_aoi_notional30_trend_pullback_1500 | 14/81 | 0 | 677.5 | 1.1695869837296622 | 2.1748538004732656 | 126.51234179027547 | max_best_day_concentration |
| market_trade15_trend_pullback_1500 | 3/81 | 0 | 245.0 | 1.1113636363636363 | 0.5907071798222834 | 70.32382480445548 | preferred_min_total_trades;max_best_day_concentration |
| opening_trade15_trend_pullback_1200 | 2/81 | 0 | 92.5 | 1.1091445427728615 | 0.48143304036122797 | 24.52142291015898 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| profile_trade15_absorption_pullback_1500 | 0/81 | 0 | -50.0 | 0.9531615925058547 | -0.16478304848104292 | 27.245602038913407 | min_total_net_profit;min_trades_per_year;preferred_min_total_trades |
