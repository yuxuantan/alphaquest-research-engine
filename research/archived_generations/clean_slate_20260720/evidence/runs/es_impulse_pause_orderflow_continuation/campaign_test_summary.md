# es_impulse_pause_orderflow_continuation campaign summary

Decision: **FAIL**

All five original variants and all five allowed per-variant rescues failed limited_core_grid_test; no variant reached monkey, WFA, Monte Carlo, simulated incubation, or acceptance validation.

Original runs: 5
Rescue runs: 5
Fixed-config core trade logs: 10
Fixed-config core equity curves: 10

| variant | run | profitable combos | profitable rate | top net | top PF | top TPY | failure |
|---|---:|---:|---:|---:|---:|---:|---|
| afternoon_large10_two_sided_impulse_pause_breakout_1530 | rescue1 | 0 | 0.000 | -495.00 | 0.964 | 73.34 | min_total_net_profit |
| afternoon_large10_two_sided_impulse_pause_breakout_1530 | run1 | 0 | 0.000 | -495.00 | 0.964 | 73.34 | min_total_net_profit |
| full_session_signed_two_sided_impulse_pause_breakout_1530 | rescue1 | 0 | 0.000 | -3225.00 | 0.866 | 84.64 | min_total_net_profit |
| full_session_signed_two_sided_impulse_pause_breakout_1530 | run1 | 0 | 0.000 | -4002.50 | 0.891 | 177.43 | min_total_net_profit |
| late_morning_large10_two_sided_impulse_pause_breakout_1230 | rescue1 | 0 | 0.000 | -1841.25 | 0.896 | 85.95 | min_total_net_profit;max_consecutive_losses |
| late_morning_large10_two_sided_impulse_pause_breakout_1230 | run1 | 0 | 0.000 | -2182.50 | 0.791 | 67.72 | min_total_net_profit;max_consecutive_losses |
| midday_signed_two_sided_impulse_pause_breakout_1400 | rescue1 | 0 | 0.000 | -3305.00 | 0.661 | 78.79 | min_total_net_profit |
| midday_signed_two_sided_impulse_pause_breakout_1400 | run1 | 0 | 0.000 | -3305.00 | 0.661 | 78.79 | min_total_net_profit |
| morning_signed_two_sided_impulse_pause_breakout_1130 | rescue1 | 0 | 0.000 | -15.00 | 0.999 | 76.70 | min_total_net_profit;max_consecutive_losses |
| morning_signed_two_sided_impulse_pause_breakout_1130 | run1 | 0 | 0.000 | -75.00 | 0.993 | 59.23 | min_total_net_profit |

CSV details: `backtest-campaigns/es_impulse_pause_orderflow_continuation/campaign_results.csv`
Trade logs manifest: `backtest-campaigns/es_impulse_pause_orderflow_continuation/trade_logs_manifest.csv`
Equity curves manifest: `backtest-campaigns/es_impulse_pause_orderflow_continuation/equity_curves_manifest.csv`
