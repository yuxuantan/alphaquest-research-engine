# ES Rolling Statistical Envelope Orderflow Reversion Campaign Summary

Decision: FAIL

All five original variants and all five one-time parameter-space/fixed-parameter rescues failed `limited_core_grid_test`.
No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Campaign results CSV: `backtest-campaigns/es_rolling_stat_envelope_orderflow_reversion/campaign_results.csv`
Trade logs manifest: `backtest-campaigns/es_rolling_stat_envelope_orderflow_reversion/trade_logs_manifest.csv`
Equity curves manifest: `backtest-campaigns/es_rolling_stat_envelope_orderflow_reversion/equity_curves_manifest.csv`

| variant | run | profitable combos | pass combos | top net | top PF | top trades/year | top failure |
|---|---:|---:|---:|---:|---:|---:|---|
| afternoon_5m_large20_24bar_reversion_1500 | rescue1 | 0/81 | 0 | -3753.75 | 0.5252924438823902 | 67.49014970436532 | min_total_net_profit |
| afternoon_5m_large20_24bar_reversion_1500 | run1 | 0/81 | 0 | -13107.5 | 0.21003465421124 | 243.04420186444761 | min_total_net_profit;max_consecutive_losses |
| all_day_1m_signed_30bar_reversion_1530 | rescue1 | 0/81 | 0 | -10149.375 | 0.6834996491775162 | 242.43838419788236 | min_total_net_profit |
| all_day_1m_signed_30bar_reversion_1530 | run1 | 0/81 | 0 | -9395.0 | 0.5360493827160494 | 243.08504867038465 | min_total_net_profit;max_consecutive_losses |
| late_morning_5m_large10_12bar_reversion_1230 | rescue1 | 0/81 | 0 | -7582.5 | 0.4513386396526773 | 107.73561151079136 | min_total_net_profit;max_consecutive_losses |
| late_morning_5m_large10_12bar_reversion_1230 | run1 | 0/81 | 0 | -10495.0 | 0.5326207971498552 | 243.0922583555262 | min_total_net_profit;max_consecutive_losses |
| midday_5m_signed_18bar_reversion_1400 | rescue1 | 0/81 | 0 | -8977.5 | 0.6137463697967086 | 187.50802139037435 | min_total_net_profit |
| midday_5m_signed_18bar_reversion_1400 | run1 | 0/81 | 0 | -13695.0 | 0.4171720395786786 | 243.0727331142031 | min_total_net_profit;max_consecutive_losses |
| morning_5m_signed_6bar_reversion_1130 | rescue1 | 0/81 | 0 | -5037.5 | 0.605752298963021 | 126.74831310709608 | min_total_net_profit;max_consecutive_losses |
| morning_5m_signed_6bar_reversion_1130 | run1 | 0/81 | 0 | -12007.5 | 0.5193635544881418 | 243.0802424512039 | min_total_net_profit;max_consecutive_losses |
