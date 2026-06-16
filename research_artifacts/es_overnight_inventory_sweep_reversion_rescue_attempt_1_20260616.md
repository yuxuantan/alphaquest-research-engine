# ES Overnight Inventory Sweep Reversion Rescue Attempt 1

Date: 2026-06-16

Decision: FAIL.

Scope: one parameter-space-only rescue for each failed variant. Entry module, stop module, target module, timeframe, data window, costs, sessions, fill assumptions, and core economic mechanic were unchanged.

Changed parameter space:

- `entry.params.min_overnight_range_points`: `[3.0, 6.0, 10.0]`
- `entry.params.reclaim_buffer_ticks`: `[0, 1, 3]`
- `sl.params.stop_pct`: `[0.0015, 0.0025, 0.004]`
- `tp.params.target_r_multiple`: `[0.75, 1.25, 1.75]`

Result: all five rescues failed `limited_core_grid_test`. No rescue reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No second rescue is permitted for these variants.

Campaign summary: `backtest-campaigns/es_overnight_inventory_sweep_reversion/campaign_test_summary.json`.
