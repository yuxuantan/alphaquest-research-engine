# ES Overnight-Intraday Reversal Rescue Attempt 1

Date: 2026-06-15

Decision: FAIL

## Scope

Campaign: `es_overnight_intraday_reversal`

Rescued variant: `high_overnight_first15_short_1000`

Config:
`campaigns/es_overnight_intraday_reversal/rescue_attempts/parameter_space_rescue_1/high_overnight_first15_short_1000/config.yaml`

Report:
`backtest-campaigns/es_overnight_intraday_reversal/high_overnight_first15_short_1000/ES/rescue1/campaign_test_summary.json`

## Rescue Rule

This rescue was originally allowed after all five campaign variants failed; the
current clarified policy allows one rescue per failed variant. It changed only
existing threshold and stop/target parameter space. It did not change:

- entry module: `overnight_intraday_reversal`
- setup mode: `high_overnight_first15_short_1000`
- direction: `short_only`
- confirmation-window length: `15` minutes
- entry time: `10:00:00`
- stop module: `percent_from_entry`
- target module: `fixed_r`
- timeframe: `5m`
- data window
- costs, fill assumptions, prop rules, or stage criteria

## Predeclared Rescue Change

The original high-overnight short-only variant had a profitable top row with
PF/MAR above threshold, but failed core surface robustness and trade-density
requirements. The rescue tested the same short-only first-15-minute reversal
mechanic with a less sparse threshold neighborhood:

- grid `entry.params.min_abs_overnight_bps`: `[20, 30, 40]`
- grid `entry.params.confirm_threshold_bps`: `[0, 2.5, 5]`
- grid `sl.params.stop_pct`: `[0.005, 0.006, 0.007]`
- grid `tp.params.target_r_multiple`: `[1.5, 2.0, 2.5]`

Total combinations: `81`.

## Result

Terminal stage: `limited_core_grid_test`.

Core grid:

- `56/81` combinations profitable.
- Profitable-combo rate: `0.691358024691358`, below the required `0.70`.
- Benchmark-passing combinations: `0`.
- Apex rule-violating iterations: `0`.

Top row:

- Params: `min_abs_overnight_bps=40`, `confirm_threshold_bps=0`,
  `stop_pct=0.007`, `target_r_multiple=2.0`.
- Trades: `54`.
- Trades per year: `36.92146896327592`.
- Net profit: `$3,842.50`.
- PF: `1.4204`.
- MAR: `1.4504`.
- Failure: `min_trades_per_year;preferred_min_total_trades`.

## Interpretation

The rescue did not repair the core failure. The strongest pocket remains a
sparse, high-threshold short-only expression. Lowering the threshold improves
density but does not produce enough robust profitable combinations or benchmark
passes. The branch did not earn monkey, WFA, Monte Carlo, or acceptance testing.

No further rescue attempt is permitted for this variant under the current
methodology.
