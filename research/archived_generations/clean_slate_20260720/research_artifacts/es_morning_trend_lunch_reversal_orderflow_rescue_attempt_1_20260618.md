# es_morning_trend_lunch_reversal_orderflow Rescue Attempt 1

- Scope: one rescue per failed variant.
- Allowed changes used: parameter space only; entry mechanics, data, timeframe, costs, fills, validation gates, and prop rules unchanged.
- Rescue entry grid: min_morning_return_ticks [16, 20, 24], min_counterflow_imbalance [0.04, 0.06, 0.08].
- Rescue target grid: target_r_multiple [0.25, 0.5, 0.75].
- Result: all five rescues failed `limited_core_grid_test`; best rescue had 1/81 profitable combinations and failed density/concentration gates.

Details: `backtest-campaigns/es_morning_trend_lunch_reversal_orderflow/campaign_results.csv`
