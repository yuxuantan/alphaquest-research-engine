# Campaign Test Summary: es_nq_nonconfirming_vap_aoi_trap

Verdict: FAIL

All eight predeclared NQ-nonconfirming VAP/AOI trap variants failed limited_core_grid_test. No variant reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

## Best Limited-Core Variant

- Variant: `market_beyond_poc_nq60_1500`
- Profitable iterations: 1/81
- Benchmark-passing combinations: 0
- Top net profit: 157.5
- Top profit factor: 1.0230515916575191
- Top MAR: 0.07073081108485517
- Top trades/year: 63.28194793280293
- Top failure reason: max_consecutive_losses;max_best_day_concentration

## Variant Results

| variant | profitable | benchmark | top_net | top_pf | top_mar | top_tpy | failure |
|---|---:|---:|---:|---:|---:|---:|---|
| market_beyond_poc_nq60_1500 | 1/81 | 0 | 157.5 | 1.0230515916575191 | 0.07073081108485517 | 63.28194793280293 | max_consecutive_losses;max_best_day_concentration |
| market_beyond_poc_nq15_1500 | 0/81 | 0 | -1435.0 | 0.855196770938446 | -0.3765782550601424 | 76.43732400576845 | min_total_net_profit;max_consecutive_losses |
| market_deep_probe_beyond_poc_nq30_1500 | 0/81 | 0 | -1662.5 | 0.742846094354215 | -0.4546490451045519 | 50.54294555169034 | min_total_net_profit;max_consecutive_losses;preferred_min_total_trades |
| opening_beyond_poc_nq30_1500 | 0/81 | 0 | -1915.0 | 0.7303766279479057 | -0.44460173805125736 | 58.2194716981132 | min_total_net_profit;max_consecutive_losses |
| all_market_beyond_poc_nq30_1500 | 0/81 | 0 | -2150.0 | 0.5034642032332564 | -0.5964253525440097 | 48.14656919797566 | min_total_net_profit;min_trades_per_year;max_consecutive_losses;preferred_min_total_trades |
| overnight_beyond_poc_nq30_1530 | 0/81 | 0 | -2202.5 | 0.46799516908212563 | -0.6558928977308438 | 50.20999359217461 | min_total_net_profit;max_consecutive_losses;preferred_min_total_trades |
| market_beyond_poc_nq30_1500 | 0/81 | 0 | -2780.0 | 0.7089767076681497 | -0.47340684750335005 | 76.05741889238634 | min_total_net_profit;max_consecutive_losses |
| market_near_value_nq30_1500 | 0/81 | 0 | -3417.5 | 0.6494871794871795 | -0.4999385774813196 | 76.05741889238634 | min_total_net_profit;max_consecutive_losses |
