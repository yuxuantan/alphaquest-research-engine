# ES VWAP Pullback Continuation - Campaign Summary

Decision: FAIL

All five original VWAP pullback-continuation variants failed before WFA, and all five one-time parameter-space-only rescues also failed. The midday trend-reclaim rescue reached monkey but failed robustness; the other rescues failed the limited core-grid gate.

| Variant | Run | Terminal stage | Profitable combos | Monkey profitable | Top net | Top PF | Top MAR | Top trades | Best-day concentration |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `failed_vwap_break_two_sided` | `run1` | `limited_core_grid_test` | 0.12345679012345678 |  | 1161.25 | 1.3963310580204777 | 1.2883140957653807 | 34 | 0.2109795479009688 |
| `failed_vwap_break_two_sided` | `rescue1` | `limited_core_grid_test` | 0.24691358024691357 |  | 2180.0 | 2.768762677484787 | 4.606048244714533 | 9 | 0.32454128440366975 |
| `midday_trend_reclaim_two_sided` | `run1` | `limited_core_grid_test` | 0.2222222222222222 |  | 3295.0 | 1.5512337933918863 | 2.517505592671264 | 61 | 0.1255690440060698 |
| `midday_trend_reclaim_two_sided` | `rescue1` | `limited_monkey_test` | 0.8148148148148148 | 0.18 | 3392.5 | 1.3551426328186338 | 1.4236334372627617 | 89 | 0.12196020633750922 |
| `morning_opening_drive_pullback_long` | `run1` | `limited_core_grid_test` | 0.1728395061728395 |  | 1526.25 | 1.2343570057581574 | 0.7892620545932117 | 51 | 0.2588042588042588 |
| `morning_opening_drive_pullback_long` | `rescue1` | `limited_core_grid_test` | 0.14814814814814814 |  | 1807.5 | 1.2726244343891402 | 0.9729418677370443 | 51 | 0.2946058091286307 |
| `morning_opening_drive_pullback_short` | `run1` | `limited_core_grid_test` | 0.037037037037037035 |  | 591.25 | 1.1078923357664234 | 0.193947929602365 | 58 | 0.44608879492600423 |
| `morning_opening_drive_pullback_short` | `rescue1` | `limited_core_grid_test` | 0.2345679012345679 |  | 1988.125 | 1.2218270571827057 | 0.4591222845416591 | 58 | 0.25055014146494814 |
| `morning_trend_reclaim_two_sided` | `run1` | `limited_core_grid_test` | 0.012345679012345678 |  | 184.375 | 1.035236502627807 | 0.0861422724004922 | 80 | 0.6169491525423729 |
| `morning_trend_reclaim_two_sided` | `rescue1` | `limited_core_grid_test` | 0.1111111111111111 |  | 725.0 | 1.3148751357220412 | 0.7547516117987276 | 35 | 0.21724137931034482 |
