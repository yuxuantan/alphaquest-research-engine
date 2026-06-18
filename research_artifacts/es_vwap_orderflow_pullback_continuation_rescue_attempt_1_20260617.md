# ES VWAP Orderflow Pullback Continuation Rescue Attempt 1 - 2026-06-17

Scope: one allowed rescue per failed variant after all five original variants
failed `limited_core_grid_test`.

Allowed changes used:

- Fixed `entry.params.min_drive_points` changed from `2.0` to `1.0`.
- `entry.params.min_orderflow_imbalance` grid changed from `[0.02, 0.04, 0.06]` to `[0.0, 0.02, 0.04]`.
- `sl.params.stop_pct` grid changed from `[0.0015, 0.0025, 0.004]` to `[0.001, 0.0015, 0.0025]`.
- `tp.params.target_r_multiple` grid changed from `[0.75, 1.0, 1.5]` to `[0.5, 0.75, 1.0]`.

Unchanged:

- Entry module: `vwap_orderflow_pullback_continuation`
- Stop module: `percent_from_entry`
- Target module: `fixed_r`
- VWAP trend-reclaim plus same-bar aggregate orderflow confirmation mechanic
- Variant time windows
- Flow mode per variant
- Data source, costs, slippage, tick size, point value, sessions, prop rules,
  fill handling, and staged validation criteria

Results:

| Variant | Rescue report | Terminal stage | Profitable combo rate |
| --- | --- | --- | ---: |
| `morning_signed_trend_reclaim_two_sided` | `backtest-campaigns/es_vwap_orderflow_pullback_continuation/morning_signed_trend_reclaim_two_sided/ES/rescue1/campaign_test_summary.json` | `limited_core_grid_test` | 0.0 |
| `morning_large10_trend_reclaim_two_sided` | `backtest-campaigns/es_vwap_orderflow_pullback_continuation/morning_large10_trend_reclaim_two_sided/ES/rescue1/campaign_test_summary.json` | `limited_core_grid_test` | 0.0 |
| `morning_large20_trend_reclaim_two_sided` | `backtest-campaigns/es_vwap_orderflow_pullback_continuation/morning_large20_trend_reclaim_two_sided/ES/rescue1/campaign_test_summary.json` | `limited_core_grid_test` | 0.0 |
| `midday_large10_trend_reclaim_two_sided` | `backtest-campaigns/es_vwap_orderflow_pullback_continuation/midday_large10_trend_reclaim_two_sided/ES/rescue1/campaign_test_summary.json` | `limited_core_grid_test` | 0.0 |
| `midday_large20_trend_reclaim_two_sided` | `backtest-campaigns/es_vwap_orderflow_pullback_continuation/midday_large20_trend_reclaim_two_sided/ES/rescue1/campaign_test_summary.json` | `limited_core_grid_test` | 0.0 |

Decision: FAIL. No rescue reached monkey, WFA, Monte Carlo, simulated
incubation, frozen validation, or candidate reporting.
