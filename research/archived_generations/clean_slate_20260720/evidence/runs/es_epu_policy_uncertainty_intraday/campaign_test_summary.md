# ES Daily Economic Policy Uncertainty Intraday

Decision: FAIL.

All five original EPU policy-uncertainty variants failed limited_core_grid_test. Each failed variant received exactly one parameter-space-only rescue, preserving the same 30-calendar-day EPU availability lag, setup mode, direction, entry time, entry module, stop module, take-profit module, timeframe, data window, costs, and validation gates. All five rescues also failed limited_core_grid_test; the best rescue was low_epu_long_1030/rescue1 with profitable-combo rate 0.4074074074074074, zero benchmark-passing combinations, top net 2170.625, PF 1.1913709499669385, and 99 top-combo trades. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or frozen validation.

| Variant | Run | Terminal stage | Core profitable rate | Top net | Top PF | Top MAR | Top trades | Failure |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `high_epu_short_1000` | `run1` | `limited_core_grid_test` | 0.0 | -3466.25 | 0.5801029678982434 | -0.769520771447629 | 107 | summary.percentage_profitable_iterations=0.0 |
| `high_epu_short_1000` | `rescue1` | `limited_core_grid_test` | 0.0 | -2808.75 | 0.6025822426600637 | -0.7440761724460946 | 93 | summary.percentage_profitable_iterations=0.0 |
| `low_epu_long_1030` | `run1` | `limited_core_grid_test` | 0.1111111111111111 | 922.5 | 1.0687406855439643 | 0.3706605463987223 | 118 | summary.percentage_profitable_iterations=0.1111111111111111 |
| `low_epu_long_1030` | `rescue1` | `limited_core_grid_test` | 0.4074074074074074 | 2170.625 | 1.1913709499669385 | 0.8986670517322473 | 99 | summary.percentage_profitable_iterations=0.4074074074074074 |
| `rising_epu_short_1130` | `run1` | `limited_core_grid_test` | 0.0 | -330.0 | 0.9821235102925244 | -0.059555914356890775 | 131 | summary.percentage_profitable_iterations=0.0 |
| `rising_epu_short_1130` | `rescue1` | `limited_core_grid_test` | 0.14814814814814814 | 2732.5 | 1.1357258164659134 | 0.40761070773834635 | 131 | summary.percentage_profitable_iterations=0.14814814814814814 |
| `falling_epu_long_1200` | `run1` | `limited_core_grid_test` | 0.0 | -3712.5 | 0.7516307074761666 | -0.5387300559877009 | 115 | summary.percentage_profitable_iterations=0.0 |
| `falling_epu_long_1200` | `rescue1` | `limited_core_grid_test` | 0.0 | -2894.375 | 0.7276523171018584 | -0.49042560782930267 | 97 | summary.percentage_profitable_iterations=0.0 |
| `high_epu_ma_short_1330` | `run1` | `limited_core_grid_test` | 0.0 | -3085.0 | 0.49959448499594483 | -1.812710043666681 | 92 | summary.percentage_profitable_iterations=0.0 |
| `high_epu_ma_short_1330` | `rescue1` | `limited_core_grid_test` | 0.0 | -2270.0 | 0.5256008359456635 | -1.8584022132132327 | 79 | summary.percentage_profitable_iterations=0.0 |
