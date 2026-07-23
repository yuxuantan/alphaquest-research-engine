# Campaign Test Summary

Campaign: `es_key_reversal_orderflow_reversal`

Final decision: FAIL

All five original variants and all five one-time parameter-space/fixed-parameter rescues failed `limited_core_grid_test`.

Best original: `afternoon_large20_two_sided_key_reversal_1530/run1`, top net `-1534.375`, PF `0.7911704661449472`, trades/year `100.51056449402189`.
Best rescue: `midday_signed_two_sided_key_reversal_1400/rescue1`, top net `-1720.0`, PF `0.7959667852906287`, trades/year `80.48603404398688`.

No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Results CSV: `backtest-campaigns/es_key_reversal_orderflow_reversal/campaign_results.csv`
Trade logs manifest: `backtest-campaigns/es_key_reversal_orderflow_reversal/trade_logs_manifest.csv`
Equity curves manifest: `backtest-campaigns/es_key_reversal_orderflow_reversal/equity_curves_manifest.csv`
