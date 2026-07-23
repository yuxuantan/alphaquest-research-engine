# es_opening_drive_mes_crowding_reversal Campaign Test Summary

Decision: FAIL.

All five original variants and all five one-time rescues failed `limited_core_grid_test`. No run reached monkey, WFA, Monte Carlo, incubation, frozen validation, or candidate reporting.

Best run by profit factor: `od30_trade_failed_extension_reversal_1300/rescue1` with top PF `1.2067502766506824`, top net `1401.25`, profitable-combo rate `0.24691358024691357`, and top trades/year `158.97991972245975`.

| variant | run | profitable rate | pass combos | top net | top PF | top trades/year | top failure |
|---|---|---:|---:|---:|---:|---:|---|
| od15_notional_failed_extension_reversal_1130 | rescue1 | 0.1111111111111111 | 2 | 870.0 | 1.1233605104572846 | 142.98277110411897 | core_profitable_rate_below_70pct |
| od15_notional_failed_extension_reversal_1130 | run1 | 0.0 | 0 | -243.75 | 0.9649910233393177 | 141.56786218962384 | min_total_net_profit |
| od15_trade_failed_extension_reversal_1130 | rescue1 | 0.06172839506172839 | 0 | 481.25 | 1.065077755240027 | 141.56710010308808 | max_best_day_concentration |
| od15_trade_failed_extension_reversal_1130 | run1 | 0.0 | 0 | -263.75 | 0.9625886524822695 | 140.1521835677276 | min_total_net_profit |
| od30_notional_failed_extension_reversal_1300 | rescue1 | 0.35802469135802467 | 6 | 1425.0 | 1.1796973518284994 | 143.9715780738555 | core_profitable_rate_below_70pct |
| od30_notional_failed_extension_reversal_1300 | run1 | 0.345679012345679 | 6 | 1425.0 | 1.1796973518284994 | 143.9715780738555 | core_profitable_rate_below_70pct |
| od30_trade_failed_extension_reversal_1300 | rescue1 | 0.24691358024691357 | 9 | 1401.25 | 1.2067502766506824 | 158.97991972245975 | core_profitable_rate_below_70pct |
| od30_trade_failed_extension_reversal_1300 | run1 | 0.012345679012345678 | 0 | 32.5 | 1.0047427946005107 | 158.97991972245975 | max_best_day_concentration |
| od60_notional_failed_extension_reversal_1530 | rescue1 | 0.0 | 0 | -1008.125 | 0.7203536754507628 | 127.02378112775499 | min_total_net_profit |
| od60_notional_failed_extension_reversal_1530 | run1 | 0.0 | 0 | -1902.5 | 0.6784959864807774 | 136.14563937840293 | min_total_net_profit |
