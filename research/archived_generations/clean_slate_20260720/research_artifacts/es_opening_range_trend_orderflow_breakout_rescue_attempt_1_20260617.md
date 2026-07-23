# ES Opening-Range Trend Orderflow Breakout Rescue Attempt 1

Date: 2026-06-17

Campaign: `es_opening_range_trend_orderflow_breakout`

Trigger: all five original variants failed `limited_core_grid_test`.

Allowed scope: one rescue per failed variant, changing only fixed parameters or declared parameter space inside existing entry, stop, and target modules.

Changes applied:

- Entry module unchanged: `opening_range_trend_orderflow_breakout`.
- Stop module unchanged: `opening_range_edge`.
- Target module unchanged: `fixed_r`.
- Data, timeframe, costs, slippage, tick size, point value, sessions, prop rules, and stage criteria unchanged.
- `entry.params.max_opening_range_pct_of_open` kept at `[0.0045, 0.0065, 0.009]`.
- Signed-flow `entry.params.min_orderflow_imbalance` changed to `[0.02, 0.04, 0.06]`.
- Large-flow `entry.params.min_orderflow_imbalance` changed to `[0.03, 0.05, 0.08]`.
- `sl.params.stop_offset_ticks` changed from `[0, 2, 4]` to `[4, 8, 12]`.
- `tp.params.target_r_multiple` changed from `[0.75, 1.0, 1.5]` to `[1.25, 1.5, 2.0]`.

Pre-PnL rescue density check:

| Variant | Rescue raw signals/year range | Eligible |
|---|---:|---|
| `or15_signed_trend_breakout_1030` | 95.1 to 155.7 | yes |
| `or15_large10_trend_breakout_1030` | 108.6 to 153.1 | yes |
| `or30_signed_trend_breakout_1100` | 97.1 to 170.1 | yes |
| `or30_large20_trend_breakout_1130` | 110.5 to 171.8 | yes |
| `or60_signed_trend_breakout_1200` | 69.8 to 147.9 | yes |

Result: FAIL.

All five parameter-space-only rescues failed `limited_core_grid_test` before monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

| Variant | Top net | Top PF | Top MAR | Trades/year | Failure |
|---|---:|---:|---:|---:|---|
| `or15_large10_trend_breakout_1030` | -8475.62 | 0.7606 | -0.5773 | 138.24 | min_total_net_profit |
| `or15_signed_trend_breakout_1030` | -8645.62 | 0.8176 | -0.5040 | 176.06 | min_total_net_profit |
| `or30_large20_trend_breakout_1130` | -7030.00 | 0.7301 | -0.5884 | 108.63 | min_total_net_profit |
| `or30_signed_trend_breakout_1100` | -9077.50 | 0.6871 | -0.6106 | 109.93 | min_total_net_profit |
| `or60_signed_trend_breakout_1200` | -3587.50 | 0.8387 | -0.5566 | 98.17 | min_total_net_profit |
