# ES Opening-Drive MES Crowding Reversal Rescue Attempt 1

Date: 2026-06-19

Decision: FAIL.

Rescue scope: one parameter-space/fixed-parameter rescue per failed variant. Modules, data, costs, fills, sessions, prop rules, and staged benchmarks were preserved.

Pre-PnL rescue density: `research_artifacts/es_opening_drive_mes_crowding_reversal_rescue1_density_audit_20260619.md` passed for all five rescues.

| variant | profitable rate | pass combos | top net | top PF | top trades/year | terminal stage |
|---|---:|---:|---:|---:|---:|---|
| od15_notional_failed_extension_reversal_1130 | 0.1111111111111111 | 2 | 870.0 | 1.1233605104572846 | 142.98277110411897 | limited_core_grid_test |
| od15_trade_failed_extension_reversal_1130 | 0.06172839506172839 | 0 | 481.25 | 1.065077755240027 | 141.56710010308808 | limited_core_grid_test |
| od30_notional_failed_extension_reversal_1300 | 0.35802469135802467 | 6 | 1425.0 | 1.1796973518284994 | 143.9715780738555 | limited_core_grid_test |
| od30_trade_failed_extension_reversal_1300 | 0.24691358024691357 | 9 | 1401.25 | 1.2067502766506824 | 158.97991972245975 | limited_core_grid_test |
| od60_notional_failed_extension_reversal_1530 | 0.0 | 0 | -1008.125 | 0.7203536754507628 | 127.02378112775499 | limited_core_grid_test |

Conclusion: all rescues failed the required `>=70%` profitable-combination limited-core gate. No further rescue is allowed for these failed variants.
