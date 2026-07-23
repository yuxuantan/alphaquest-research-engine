# Core Grid and Monkey Archive Comparison - 2026-06-17

Decision: NEEDS MANUAL REVIEW for archived limited-core/limited-monkey passes
when compared with the current methodology.

## Current Checkout Behavior

Current staged criteria in `src/propstack/research/campaign_stages.py` require:

- limited core grid:
  - valid parameter-combination count: fixed `1` or tunable `8-120`;
  - `summary.percentage_profitable_iterations >= 0.70`;
  - `summary.number_passing_benchmark >= 1`;
  - zero prop-rule violations.
- limited monkey:
  - core beats constrained random monkey paths on net profit and drawdown;
  - actual trade-path stress is enabled;
  - stressed actual trade path has at least 80% profitable paths;
  - stressed median net profit is positive;
  - one-tick-worse slippage remains profitable;
  - zero prop-rule violations.

This separates two different questions:

- random-placebo monkey: does the strategy beat randomized trades?
- actual trade-path stress: does the strategy itself survive worse execution,
  missed trades, entry delay, time-window jitter, and pessimistic fill ordering?

## Archived Difference

Archived limited-core passes generally used:

- `summary.total_combinations_tested >= 100`;
- `summary.percentage_profitable_iterations >= 0.70`;
- zero prop-rule violations.

They did not require `summary.number_passing_benchmark >= 1`.

Archived limited-monkey passes generally used:

- `summary.core_beats_monkey_net_profit_rate >= 0.90`;
- `summary.core_beats_monkey_max_drawdown_rate >= 0.90`;
- zero prop-rule violations.

They did not include the current `trade_path_stress` block.

## Evidence Scan

Scan scope: `_archived/reports/**/{limited_core_grid_test,limited_monkey_test}/stage_result.json`.

- Archived limited-core stages marked passed: 96.
- Archived passed limited-core stages with `number_passing_benchmark == 0`: 96.
- Archived passed limited-core stages with more than 120 combinations: 27.
- Archived limited-monkey stages marked passed: 57.
- Archived passed limited-monkey stages without `trade_path_stress`: 57.
- Archived passed limited-monkey stages whose random-placebo median net profit was non-positive: 39.

Examples:

- `_archived/reports/morning_orderflow_momentum/.../two_sided_signed_flow_1515_flatten_continuation/.../limited_core_grid_test/stage_result.json`
  passed archived core with 180 combinations and 96.7% profitable iterations,
  but `number_passing_benchmark` was 0.
- The same archived run passed limited monkey because the strategy beat random
  paths, even though random-placebo median net profit was `-3542.5`; no actual
  `trade_path_stress` result exists in that artifact.

## Active Volume-Shock Run

`backtest-campaigns/es_volume_shock_liquidity_reversal/morning_down_shock_reversal_long/ES/run1`
halted at limited core.

Note: the saved `stage_result.json` for this run was produced before the
current `summary.number_passing_benchmark >= 1` limited-core criterion was
added to `DEFAULT_STAGE_CRITERIA`. The saved result therefore contains only the
combination-count, profitable-grid-rate, and prop-rule criteria. The summary
still records `number_passing_benchmark: 0`.

Core grid summary:

- combinations tested: 81;
- profitable combinations: 5;
- profitable rate: 6.17%;
- full-benchmark-passing combinations: 0;
- prop-rule violating combinations: 0.

This fails both the archived core criterion (`>=70%` profitable combinations)
and the current stricter criterion. Its failure is not explained by the
current archive-vs-current gate difference.

## Conclusion

The current methodology is materially stricter than the archived methodology.
That means archived passes should not be interpreted as current-methodology
passes without rerunning them. However, the current `morning_down_shock_reversal_long`
failure is a genuine limited-core failure under both old and current core gates.

Focused verification on the current checkout:

`python3 -m pytest tests/test_campaign_stages.py tests/test_monkey.py tests/test_core_grid.py`

Result: PASS, 46 tests.
