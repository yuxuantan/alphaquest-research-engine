# nq_pivot_filtered_mes_participation_crowding_reversion Final Pre-PnL Density Audit

Date: 2026-06-22

Initial exact density audit: `research_artifacts/nq_pivot_filtered_mes_participation_crowding_reversion_density_audit_20260622.md`.
The initial ES threshold grid failed only for `morning_notional_down_reversal_long_window_1100` after the completed-pivot filter. Before any NQ PnL was inspected, that variant was reformulated by lowering only `entry.params.base_params.share_rank_min` from `[0.45, 0.55, 0.65]` to `[0.35, 0.40, 0.45]`. Direction, signal window, pivot filter, lookback, stops, targets, data, costs, and validation gates were unchanged.

Decision: PASS. Every final declared entry-grid corner is above 50 signals/year.

## Variant Summary

| variant_id | min | max | mean |
| --- | --- | --- | --- |
| afternoon_trade_two_sided_reversal_window_1500 | 77.583944 | 104.337028 | 91.758385 |
| late_morning_trade_two_sided_reversal_window_1200 | 73.359773 | 101.239302 | 87.987921 |
| midday_notional_two_sided_reversal_window_1330 | 108.561199 | 147.141962 | 127.867226 |
| morning_notional_down_reversal_long_window_1100 | 55.195837 | 61.532093 | 58.481303 |
| morning_notional_two_sided_reversal_window_1130 | 89.83404 | 119.68485 | 104.822025 |

## Controls

- Counts use the actual `market_structure_filtered_entry` wrapper and one accepted signal per session.
- The base MES participation module uses `return_column_prefix: nq`.
- This is a density-only reformulation made before NQ PnL, trade logs, equity curves, or best parameters were inspected.
