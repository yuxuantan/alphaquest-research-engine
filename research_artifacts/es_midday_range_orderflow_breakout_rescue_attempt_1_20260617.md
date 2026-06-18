# ES Midday Range Orderflow Breakout Rescue Attempt 1

Date: 2026-06-17

Campaign: `es_midday_range_orderflow_breakout`

Trigger: all five original variants failed `limited_core_grid_test`.

Allowed scope: one rescue per failed variant, changing only fixed parameters or
declared parameter space inside the existing entry, stop, and target modules.

Changes applied:

- Entry module unchanged: `intraday_range_orderflow_breakout`.
- Stop module unchanged: `opening_range_retest_boundary`.
- Target module unchanged: `fixed_r`.
- Data, timeframe, costs, slippage, tick size, point value, sessions, prop
  rules, and stage criteria unchanged.
- `entry.params.max_range_points` changed from `[8,12,16]` to `[6,8,10]`.
- `entry.params.min_orderflow_imbalance` grid kept within the original flow
  family thresholds: signed `[0.0,0.03,0.06]`; large-flow `[0.0,0.05,0.10]`.
- `sl.params.stop_offset_ticks` changed from `[4,8,12]` to `[8,12,16]`.
- `tp.params.target_r_multiple` changed from `[0.75,1.0,1.5]` to
  `[1.25,1.5,2.0]`.
- Fixed defaults were moved to the center of the rescue grid:
  `max_range_points=8`, middle flow threshold, `stop_offset_ticks=12`,
  `target_r_multiple=1.5`.

Pre-PnL density check for rescue entry grids:

| Variant | Rescue Raw Signals/Year Range | Eligible |
| --- | --- | --- |
| `lunch_1130_1300_signed_breakout_1430` | 51.9 to 90.1 | yes |
| `lunch_1130_1300_large10_breakout_1430` | 50.9 to 89.7 | yes |
| `lunch_1130_1300_large20_breakout_1430` | 50.9 to 89.0 | yes |
| `late_lunch_1200_1330_signed_breakout_1500` | 59.2 to 100.1 | yes |
| `late_lunch_1200_1330_large10_breakout_1500` | 57.1 to 98.8 | yes |

Interpretation before running rescue PnL: the original variants were not sparse;
they were unprofitable. This rescue only tests whether the same edge needs
tighter range compression and larger excursion payoff to overcome costs. It is
not a direction flip, filter addition, data change, or stage-gate change.

Result: FAIL.

All five rescue runs failed `limited_core_grid_test` with `0.0` profitable
core-grid combinations. No rescue reached limited monkey, WFA, WFA OOS monkey,
Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Best rescue by top net profit and PF:

- Variant: `lunch_1130_1300_large20_breakout_1430`
- Run: `rescue1`
- Profitable combo rate: `0.0`
- Top net profit: `-2433.75`
- Top profit factor: `0.8948704103671706`
- Top trades/year: `145.69529085872577`
- Top failure reason: `min_total_net_profit`
