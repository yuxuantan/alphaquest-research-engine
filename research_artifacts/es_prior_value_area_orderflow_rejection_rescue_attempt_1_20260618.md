# es_prior_value_area_orderflow_rejection Rescue Attempt 1

- Scope: one rescue per failed variant.
- Allowed changes used: stop/target parameter space only; entry mechanics, data, timeframe, costs, fills, validation gates, and prop rules unchanged.
- Rescue stop grid: `sl.params.stop_offset_ticks: [0, 1, 2]`.
- Rescue target grid: `tp.params.target_r_multiple: [0.25, 0.4, 0.6]`.
- Result: all five rescues failed `limited_core_grid_test` with 0 profitable combinations.

Details: `backtest-campaigns/es_prior_value_area_orderflow_rejection/campaign_results.csv`
