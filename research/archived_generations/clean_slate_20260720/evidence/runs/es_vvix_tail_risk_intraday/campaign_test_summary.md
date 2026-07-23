# ES VVIX Tail Risk Intraday

Decision: FAIL.

All five original VVIX tail-risk variants failed limited_core_grid_test. Each failed variant received exactly one parameter-space-only rescue, preserving the same Cboe prior-close feature construction, setup mode, direction, entry time, entry module, stop module, take-profit module, timeframe, data window, costs, and stage criteria. Four rescues failed limited_core_grid_test. The low_vvix_long_1030 rescue passed core with a 0.9629629629629629 profitable-combo rate, but failed limited_monkey_test: only 0.31666666666666665 random-placebo runs were profitable and median net profit was -1482.5. No run reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or frozen validation.

| Variant | Run | Terminal stage | Core profitable rate | Top net | Top PF | Top MAR | Top trades | Failure |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `high_vvix_short_1000` | `run1` | `limited_core_grid_test` | 0.0 | -3727.5 | 0.805985686402082 | -0.6650068349490418 | 208 | summary.percentage_profitable_iterations=0.0 |
| `high_vvix_short_1000` | `rescue1` | `limited_core_grid_test` | 0.0 | -2330.0 | 0.8537350910232266 | -0.5913886924890512 | 151 | summary.percentage_profitable_iterations=0.0 |
| `low_vvix_long_1030` | `run1` | `limited_core_grid_test` | 0.5185185185185185 | 1245.0 | 1.2081939799331103 | 1.0872965866318864 | 56 | summary.percentage_profitable_iterations=0.5185185185185185 |
| `low_vvix_long_1030` | `rescue1` | `limited_monkey_test` | 0.9629629629629629 | 3041.25 | 1.6872881355932203 | 1.8214174302938066 | 48 | monkey_profitable_rate=0.31666666666666665; monkey_median_net=-1482.5 |
| `rising_vvix_short_1130` | `run1` | `limited_core_grid_test` | 0.0 | -2270.0 | 0.8563518430628065 | -0.5456571835317245 | 114 | summary.percentage_profitable_iterations=0.0 |
| `rising_vvix_short_1130` | `rescue1` | `limited_core_grid_test` | 0.4444444444444444 | 1972.5 | 1.1499714883102072 | 0.7941553943534794 | 83 | summary.percentage_profitable_iterations=0.4444444444444444 |
| `falling_vvix_long_1200` | `run1` | `limited_core_grid_test` | 0.0 | -2360.0 | 0.7997029492892 | -0.4528252267285824 | 107 | summary.percentage_profitable_iterations=0.0 |
| `falling_vvix_long_1200` | `rescue1` | `limited_core_grid_test` | 0.0 | -476.25 | 0.9639409426462238 | -0.12285232460216211 | 94 | summary.percentage_profitable_iterations=0.0 |
| `high_vvix_vix_ratio_short_1330` | `run1` | `limited_core_grid_test` | 0.0 | -5185.0 | 0.6362679761487198 | -0.6556894664714591 | 137 | summary.percentage_profitable_iterations=0.0 |
| `high_vvix_vix_ratio_short_1330` | `rescue1` | `limited_core_grid_test` | 0.0 | -4627.5 | 0.5827321911632101 | -0.8103190634871048 | 108 | summary.percentage_profitable_iterations=0.0 |
