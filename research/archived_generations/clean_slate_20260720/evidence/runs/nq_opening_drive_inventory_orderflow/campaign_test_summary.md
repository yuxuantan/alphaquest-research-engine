# NQ opening-drive inventory orderflow campaign summary

Verdict: FAIL. No variant passed the staged flow.

| Variant | Terminal stage | Core profitable rate | Top net | Top trades | Failure note |
| --- | --- | ---: | ---: | ---: | --- |
| open30_flow_continuation_1030 | walk_forward_analysis | 1 | 1415.0 | 19 | min_trades_per_year;preferred_min_total_trades |
| open30_absorbed_pressure_fade_1015 | limited_core_grid_test | 0.111111 | 257.5 | 6 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| open60_flow_continuation_1130 | limited_monkey_test | 0.938272 | 912.5 | 9 | min_trades_per_year;preferred_min_total_trades |
| open60_exhaustion_fade_1300 | limited_core_grid_test | 0.296296 | 100.0 | 4 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| open30_price_flow_divergence_fade_1400 | limited_monkey_test | 0.740741 | 320.0 | 6 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |

