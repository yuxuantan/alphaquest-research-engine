# ES Trend-Aligned Orderflow Continuation Rescue Attempt 1 - 2026-06-17

Trigger: all five original variants failed `limited_core_grid_test`; no variant reached monkey, WFA, Monte Carlo, simulated incubation, or acceptance OOS.

Allowed rescue scope: per-failed-variant parameter-space-only rescue. No entry module, stop module, target module, data source, costs, session definition, signal time, trend horizon, flow mode, fill rule, or validation gate was changed.

Original grid:

- `entry.params.min_orderflow_imbalance`: `[0.005, 0.01]`
- `entry.params.min_trend_move_ticks`: `[0, 1]`
- `sl.params.stop_pct`: `[0.0015, 0.0025, 0.0035]`
- `tp.params.target_r_multiple`: `[0.75, 1.0, 1.5]`
- Combinations per variant: 36

Rescue grid:

- Fixed `entry.params.min_trend_move_ticks`: `0`
- `entry.params.min_orderflow_imbalance`: `[0.01, 0.02]`
- `sl.params.stop_pct`: `[0.00075, 0.001, 0.0015]`
- `tp.params.target_r_multiple`: `[0.5, 0.75, 1.0]`
- Combinations per variant: 18

Rationale before running rescue: the original failures were consistently negative in the limited core window. A defensible rescue can only ask whether the same trend-plus-flow signal needs a stricter flow threshold and shorter intraday payoff geometry. It cannot reverse direction, add filters, change the signal time, or introduce new mechanics.

Rescue entry-density check: with fixed `min_trend_move_ticks = 0`, both rescue orderflow thresholds stayed above 50 signals/year on the full local RTH history for all five variants before stop/target filtering:

| Variant | Annualized counts for `[0.01, 0.02]` |
|---|---:|
| `morning_15_30_large20_trend_flow_1030` | 65.97, 64.29 |
| `late_morning_15_30_signed_trend_flow_1130` | 61.57, 56.58 |
| `midday_15_30_large10_trend_flow_1230` | 65.52, 64.16 |
| `afternoon_30_60_large20_trend_flow_1400` | 65.71, 64.22 |
| `late_day_30_60_large10_trend_flow_1430` | 64.16, 61.89 |

Result: all five rescue variants failed `limited_core_grid_test`; no rescue reached monkey, WFA, Monte Carlo, simulated incubation, or acceptance OOS.

Least-bad rescue row: `morning_15_30_large20_trend_flow_1030/rescue1`, top net profit `-1626.25`, profit factor `0.5827453495830661`, and `65.15759441399504` trades/year. Failure reason: `min_total_net_profit`.

Status: completed_failed.
