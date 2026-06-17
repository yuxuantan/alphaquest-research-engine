# Core/Monkey Test Audit - Current vs Archived

Date: 2026-06-17

Scope: compare the current staged `limited_core_grid_test` and `limited_monkey_test`
implementation against representative `_archived` campaign-test artifacts, with
specific attention to whether current failures could be caused by changed test
mechanics rather than strategy weakness.

## Current implementation

- `limited_core_grid_test` currently requires:
  - valid parameter-combination count: fixed 1 combo or 8-120 tunable combos
  - `summary.percentage_profitable_iterations >= 0.70`
  - `summary.number_passing_benchmark >= 1`
  - `summary.apex_rule_violating_iterations <= 0`
- The core grid itself applies each dotted parameter combination to the normal
  config and runs `BacktestEngine`. It is not a separate simplified execution
  model.
- `limited_monkey_test` currently requires:
  - core beats constrained random monkey net profit at least 90% of runs
  - core beats constrained random monkey max drawdown at least 90% of runs
  - actual trade-path stress is enabled
  - trade-path stress is at least 80% profitable
  - trade-path stress median net profit is positive
  - one-tick-worse trade-path stress remains profitable
  - no prop-rule violations in stress or core metrics
- The trade-path stress perturbs the actual core trades with:
  - entry delay
  - missed trades
  - extra slippage
  - time-window trims
  - pessimistic stop-before-target handling when both are touched in the same
    stressed bar.

## Current shortlist data window

`canonicalize_campaign_config()` currently overwrites limited core/monkey stage
windows to:

```yaml
data_window:
  mode: first_months
  months: 18
```

For the open volume-shock config, this resolves to:

```text
limited_core_grid_test: 2011-01-03 through 2012-07-03, RTH
limited_monkey_test:    2011-01-03 through 2012-07-03, RTH
```

So current limited core/monkey is not "10% of all available data"; it is the
first 18 months of the configured data range unless the runner is changed.

## Difference from archived tests

Representative archived core-grid stage criteria were:

```text
summary.total_combinations_tested
summary.percentage_profitable_iterations
summary.apex_rule_violating_iterations
```

Representative archived monkey stage criteria were:

```text
summary.core_beats_monkey_net_profit_rate
summary.core_beats_monkey_max_drawdown_rate
summary.core_metrics.apex_rule_violations
```

Some older archived monkey results did not include the apex criterion. None of
the representative archived monkey summaries included current trade-path stress
criteria.

Conclusion: current monkey gating is materially stricter than archived monkey
gating. A strategy could pass archived monkey and fail current monkey solely
because it cannot survive actual trade-path perturbation or one-tick-worse
slippage. That is a stricter methodology gate, not a false negative by itself.

## Active volume-shock run state

The active generated `es_volume_shock_liquidity_reversal` stage outputs appear
to predate the current criteria/period-reporting code. Their core-stage criteria
do not include `summary.number_passing_benchmark`, and the summaries do not
include `actual_data_period`.

Existing active core results:

| Variant | Combos | Profitable Iteration Rate | Benchmark-Passing Combos |
|---|---:|---:|---:|
| afternoon_symmetric_shock_reversion | 81 | 0.0370 | 0 |
| all_day_symmetric_shock_reversion | 81 | 0.0000 | 0 |
| midday_symmetric_shock_reversion | 81 | 0.0247 | 0 |
| morning_down_shock_reversal_long | 81 | 0.0617 | 0 |
| morning_up_shock_reversal_short | 81 | 0.0494 | 0 |

Representative archived `volume_conditioned_liquidity_reversal` core results
also failed badly:

| Timeframe/Variant | Combos | Profitable Iteration Rate | Benchmark-Passing Combos |
|---|---:|---:|---:|
| 5m/high_volume_down_reversal | 108 | 0.0093 | 0 |
| 5m/high_volume_up_reversal | 108 | 0.0463 | 0 |
| 5m/symmetric_volume_shock_reversion | 108 | 0.0278 | 0 |
| 15m/high_volume_down_reversal | 108 | 0.1019 | 0 |
| 15m/high_volume_up_reversal | 108 | 0.1204 | 0 |
| 15m/symmetric_volume_shock_reversion | 108 | 0.0833 | 0 |
| 30m/high_volume_down_reversal | 108 | 0.1111 | 0 |
| 30m/high_volume_up_reversal | 108 | 0.1389 | 0 |
| 30m/symmetric_volume_shock_reversion | 108 | 0.1111 | 0 |

## Judgment

No evidence found that core-grid execution is incorrectly causing the active
volume-shock variants to fail. The core profitable-iteration rates are far below
the 70% gate, and benchmark-passing combinations are zero.

However, the archive comparison confirms that current monkey testing is stricter
than archived monkey testing. That stricter monkey gate can explain why some
older "passed monkey" archived variants would not pass current methodology.

The active generated volume-shock artifacts should not be treated as fully
current-format evidence because they lack current criteria and period
annotations. If this campaign remains of interest, rerun it under the current
runner before making a final archived-vs-current comparison.
