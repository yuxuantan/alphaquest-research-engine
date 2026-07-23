# ES Cboe Put/Call Sentiment Intraday

Decision: FAIL.

All five original Cboe put/call sentiment variants failed limited_core_grid_test. Each failed variant received exactly one parameter-space-only rescue, preserving the same Cboe strict-prior-date feature construction, setup mode, direction, entry time, entry module, stop module, take-profit module, timeframe, data window, costs, and validation gates. Three rescues failed limited_core_grid_test. The falling_total_pc_long_1130 and high_total_vs_equity_pc_short_1330 rescues passed core, but both failed limited_monkey_test. falling_total_pc_long_1130/rescue1 had random-monkey profitable rate 0.19666666666666666 and median net -2727.5; high_total_vs_equity_pc_short_1330/rescue1 had random-monkey profitable rate 0.06666666666666667, median net -3923.75, and one_tick_worse_profitable=False. No run reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or frozen validation.

| Variant | Run | Terminal stage | Core profitable rate | Top net | Top PF | Top MAR | Top trades | Failure |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `low_equity_pc_long_1000` | `run1` | `limited_core_grid_test` | 0.0 | -1615.0 | 0.8912457912457913 | -0.4698849306111513 | 108 | summary.percentage_profitable_iterations=0.0 |
| `low_equity_pc_long_1000` | `rescue1` | `limited_core_grid_test` | 0.037037037037037035 | 85.0 | 1.005031074282332 | 0.020097437142044452 | 108 | summary.percentage_profitable_iterations=0.037037037037037035 |
| `high_equity_pc_short_1030` | `run1` | `limited_core_grid_test` | 0.037037037037037035 | 1082.5 | 1.0492381168978848 | 0.36916058400562546 | 146 | summary.percentage_profitable_iterations=0.037037037037037035 |
| `high_equity_pc_short_1030` | `rescue1` | `limited_core_grid_test` | 0.6296296296296297 | 3870.0 | 1.138560687432868 | 0.5869384221465898 | 146 | summary.percentage_profitable_iterations=0.6296296296296297 |
| `falling_total_pc_long_1130` | `run1` | `limited_core_grid_test` | 0.5185185185185185 | 3262.5 | 1.2238805970149254 | 1.5534026510713692 | 125 | summary.percentage_profitable_iterations=0.5185185185185185 |
| `falling_total_pc_long_1130` | `rescue1` | `limited_monkey_test` | 1.0 | 5652.5 | 1.353060587133042 | 2.183674627589934 | 117 | monkey_profitable_rate=0.19666666666666666; monkey_median_net=-2727.5; one_tick_worse_profitable=True |
| `rising_total_pc_short_1200` | `run1` | `limited_core_grid_test` | 0.0 | -1345.0 | 0.9175478927203066 | -0.1835769149558677 | 114 | summary.percentage_profitable_iterations=0.0 |
| `rising_total_pc_short_1200` | `rescue1` | `limited_core_grid_test` | 0.5925925925925926 | 4730.0 | 1.2826411711980878 | 0.753286793529983 | 114 | summary.percentage_profitable_iterations=0.5925925925925926 |
| `high_total_vs_equity_pc_short_1330` | `run1` | `limited_core_grid_test` | 0.14814814814814814 | 1668.75 | 1.1051346668766735 | 0.4812120693489631 | 135 | summary.percentage_profitable_iterations=0.14814814814814814 |
| `high_total_vs_equity_pc_short_1330` | `rescue1` | `limited_monkey_test` | 0.8888888888888888 | 4675.0 | 1.2595780122154359 | 0.948611304480025 | 135 | monkey_profitable_rate=0.06666666666666667; monkey_median_net=-3923.75; one_tick_worse_profitable=False |
