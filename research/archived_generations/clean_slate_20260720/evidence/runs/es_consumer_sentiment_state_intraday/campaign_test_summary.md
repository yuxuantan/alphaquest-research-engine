# ES Consumer Sentiment State Intraday

Decision: FAIL.

All five original consumer-sentiment variants failed limited_core_grid_test. Each failed variant received exactly one parameter-space-only rescue, preserving the same 45-calendar-day UMCSENT availability lag, setup mode, direction, entry time, entry module, stop module, take-profit module, timeframe, data window, costs, and validation gates. All five rescues also failed limited_core_grid_test; the best rescue was high_sentiment_short_1030/rescue1 with profitable-combo rate 0.07407407407407407, zero benchmark-passing combinations, top net 140.0, PF 1.1454545454545455, and only 12 top-combo trades. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or frozen validation.

| Variant | Run | Terminal stage | Core profitable rate | Top net | Top PF | Top MAR | Top trades | Failure |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `low_sentiment_long_1000` | `run1` | `limited_core_grid_test` | 0.0 | -6332.5 | 0.8397545391282343 | -0.7164882283363786 | 269 | summary.percentage_profitable_iterations=0.0 |
| `low_sentiment_long_1000` | `rescue1` | `limited_core_grid_test` | 0.0 | -4055.0 | 0.836442472521932 | -0.6951805997404981 | 191 | summary.percentage_profitable_iterations=0.0 |
| `high_sentiment_short_1030` | `run1` | `limited_core_grid_test` | 0.0 | 0.0 | 0.0 | 0.0 | 0 | summary.percentage_profitable_iterations=0.0 |
| `high_sentiment_short_1030` | `rescue1` | `limited_core_grid_test` | 0.07407407407407407 | 140.0 | 1.1454545454545455 | 7.869801728891338 | 12 | summary.percentage_profitable_iterations=0.07407407407407407 |
| `rising_sentiment_long_1130` | `run1` | `limited_core_grid_test` | 0.0 | -1610.0 | 0.913800026770178 | -0.23802400095738174 | 197 | summary.percentage_profitable_iterations=0.0 |
| `rising_sentiment_long_1130` | `rescue1` | `limited_core_grid_test` | 0.0 | -3881.875 | 0.8570343430623332 | -0.3641077526785347 | 217 | summary.percentage_profitable_iterations=0.0 |
| `falling_sentiment_short_1200` | `run1` | `limited_core_grid_test` | 0.0 | -507.5 | 0.9586136595310907 | -0.3065023954859709 | 104 | summary.percentage_profitable_iterations=0.0 |
| `falling_sentiment_short_1200` | `rescue1` | `limited_core_grid_test` | 0.0 | -65.0 | 0.9932467532467533 | -0.06042304069347327 | 83 | summary.percentage_profitable_iterations=0.0 |
| `low_sentiment_ma_long_1330` | `run1` | `limited_core_grid_test` | 0.0 | -10890.0 | 0.5487413239407438 | -0.6745609644969454 | 363 | summary.percentage_profitable_iterations=0.0 |
| `low_sentiment_ma_long_1330` | `rescue1` | `limited_core_grid_test` | 0.0 | -9195.0 | 0.7535678391959799 | -0.5538287962719969 | 344 | summary.percentage_profitable_iterations=0.0 |
