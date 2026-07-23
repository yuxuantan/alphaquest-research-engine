# ES Prior POC Orderflow Magnet Campaign Summary

Decision: FAIL

All five original variants failed limited_core_grid_test on the configured random 10% shortlist window. Each failed variant received exactly one parameter-space rescue preserving the same POC magnet mechanic; all five rescues also failed limited_core_grid_test. No run reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or frozen validation.

## Results

| variant_id | run_id | failed_stage | core_profitable_rate | core_profitable_iterations | core_total_combinations | fixed_core_net_profit | fixed_core_total_trades |
| --- | --- | --- | --- | --- | --- | --- | --- |
| morning_above_poc_signed_magnet_short | run1 | limited_core_grid_test | 0.024691 | 2 | 81 | -3457.50 | 119 |
| morning_above_poc_signed_magnet_short | rescue1 | limited_core_grid_test | 0.024691 | 2 | 81 | -2832.50 | 109 |
| morning_below_poc_signed_magnet_long | run1 | limited_core_grid_test | 0.000000 | 0 | 81 | -6922.50 | 112 |
| morning_below_poc_signed_magnet_long | rescue1 | limited_core_grid_test | 0.000000 | 0 | 81 | -6470.00 | 114 |
| late_morning_large10_two_sided_magnet | run1 | limited_core_grid_test | 0.000000 | 0 | 81 | -5070.00 | 169 |
| late_morning_large10_two_sided_magnet | rescue1 | limited_core_grid_test | 0.000000 | 0 | 81 | -5637.50 | 160 |
| midday_signed_two_sided_magnet | run1 | limited_core_grid_test | 0.000000 | 0 | 81 | -4092.50 | 166 |
| midday_signed_two_sided_magnet | rescue1 | limited_core_grid_test | 0.012346 | 1 | 81 | -1120.00 | 154 |
| afternoon_large20_two_sided_magnet | run1 | limited_core_grid_test | 0.000000 | 0 | 81 | -7237.50 | 200 |
| afternoon_large20_two_sided_magnet | rescue1 | limited_core_grid_test | 0.000000 | 0 | 81 | -4410.00 | 202 |

## Artifacts

Results CSV: backtest-campaigns/es_prior_poc_orderflow_magnet/campaign_results.csv
Trade-log manifest: backtest-campaigns/es_prior_poc_orderflow_magnet/trade_logs_manifest.csv
Equity-curve manifest: backtest-campaigns/es_prior_poc_orderflow_magnet/equity_curves_manifest.csv
WFA table: backtest-campaigns/es_prior_poc_orderflow_magnet/wfa_table.csv
Monte Carlo summary: backtest-campaigns/es_prior_poc_orderflow_magnet/monte_carlo_summary.csv
