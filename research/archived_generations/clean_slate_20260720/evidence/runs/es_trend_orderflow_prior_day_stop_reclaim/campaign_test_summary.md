# es_trend_orderflow_prior_day_stop_reclaim Campaign Summary

Decision: FAIL

Original variants were rejected before staged PnL because the predeclared sweep-reclaim plus trend/absorbed-flow mechanic was too sparse. One parameter-space/fixed-parameter rescue was then applied to each failed variant before any PnL from this campaign was inspected.

The standalone vectorized rescue density audit was invalidated by the staged runner signal-density output, so the staged core-grid summaries are authoritative. All five rescue runs failed `limited_core_grid_test`; no run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

| variant | profitable combos | profitable rate | benchmark pass combos | top net | top PF | top trades/year | top failure |
|---|---:|---:|---:|---:|---:|---:|---|
| `late_morning_signed_two_sided_trend_absorption_1230` | 1 / 81 | 0.012346 | 0 | 36.25 | 1.019155 | 16.600526 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| `morning_pdh_signed_trend_absorption_short_1130` | 1 / 81 | 0.012346 | 0 | 36.25 | 1.019155 | 16.600526 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| `morning_pdl_signed_trend_absorption_long_1130` | 1 / 81 | 0.012346 | 0 | 36.25 | 1.019155 | 16.600526 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| `afternoon_large20_two_sided_trend_absorption_1500` | 0 / 81 | 0.000000 | 0 | -120.00 | 0.926829 | 18.375620 | min_total_net_profit;min_trades_per_year;preferred_min_total_trades |
| `midday_large10_two_sided_trend_absorption_1400` | 0 / 81 | 0.000000 | 0 | -370.00 | 0.694845 | 17.019982 | min_total_net_profit;min_trades_per_year;preferred_min_total_trades |
