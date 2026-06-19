# ES Gao Last-Half-Hour Orderflow Confirmation Rescue Attempt 2

Date: 2026-06-19

Scope: `first30_broad_large_alignment_1530` only.

Normal policy note: this is a second rescue for one failed variant. It was run only because the user explicitly requested another rescue for this variant and specifically requested a higher TP RR target and wider stop-loss distance.

Changes from rescue1:

- Entry module unchanged: `gao_last_half_hour_orderflow`
- Entry thresholds unchanged: `entry.params.min_first_return_ticks` in `[8, 12]`; `entry.params.min_orderflow_imbalance` in `[0.02, 0.03]`
- Stop module unchanged: `percent_from_entry`
- Target module unchanged: `fixed_r`
- Stop grid widened from `[0.001, 0.0015, 0.002]` to `[0.0025, 0.003, 0.0035]`
- Target grid increased from `[0.5, 0.75, 1.0]` to `[1.25, 1.5, 2.0]`
- Data, costs, fills, sessions, signal time, first-window length, and validation gates unchanged.

Preflight: PASS.

Staged result: FAIL at `limited_core_grid_test`.

- Profitable combinations: `1 / 36`
- Profitable combo rate: `0.027777777777777776`
- Benchmark-passing combinations: `0`
- Apex/flatten-violating combinations: `0`
- Best combo: `entry.params.min_first_return_ticks=12`, `entry.params.min_orderflow_imbalance=0.03`, `sl.params.stop_pct=0.0035`, `tp.params.target_r_multiple=2.0`
- Best net profit: `107.5`
- Best PF: `1.0152158527954707`
- Best trades/year: `73.45024501632395`
- Best failure reason: `max_consecutive_losses;max_best_day_concentration`

Fixed-config core trade log: `backtest-campaigns/es_gao_last_half_hour_orderflow_confirmation/first30_broad_large_alignment_1530/ES/rescue2/limited_core_grid_test/fixed_config_core_trade_log.csv`

Decision: FAIL. No WFA, monkey, Monte Carlo, simulated incubation, frozen validation, or candidate report was reached.
