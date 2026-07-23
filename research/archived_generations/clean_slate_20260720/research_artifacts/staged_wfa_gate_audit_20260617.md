# Staged WFA Gate Audit - 2026-06-17

Question: why have no active variants reached WFA, and are staged tests running
correctly compared with `_archived` reports?

Superseding correction: `research_artifacts/staged_gate_correction_audit_20260617.md`
documents a methodology fix made after this audit. The staged runner was
mechanically halting as configured, but the configured monkey gate was too
strict in the wrong place because it required random-placebo monkey paths to be
profitable. The corrected gate now uses core-beats-random rates for the placebo
test and retains profitability/median/one-tick checks for actual trade-path
stress. Two prior active monkey failures were rerun under the corrected gate;
both advanced to WFA and failed WFA early exit.

Decision: current active staged runs are behaving as configured. WFA is present
in the stage order, but current runs halt after the first failed stage. No active
variant has passed the current limited-monkey gate, so no active variant has
earned WFA.

## Current Active Evidence

Scan scope: `backtest-campaigns/*/*/*/*/campaign_test_summary.json`,
excluding `_archived`.

- Variant summaries scanned: 468.
- Limited core grid: 30 passed, 433 failed, 5 errored stale `run1` artifacts.
- Limited monkey: 30 executed, 30 failed, 438 skipped after core failure.
- WFA: 0 executed, 468 skipped.
- WFA OOS monkey / Monte Carlo / incubation / acceptance: all skipped because no
  active run passed limited monkey.

The 5 core-grid errors were old `es_market_plumbing_liquidity_capacity/run1`
artifacts with unsupported `data.feature_set:
market_plumbing_priority_lag1_no_lookahead`. Corrected `run2` and rescue
artifacts exist and failed normally; these stale errors are not evidence that
the current WFA gate is broken.

Representative current run:

- `backtest-campaigns/es_volume_shock_liquidity_reversal/morning_down_shock_reversal_long/ES/run1/campaign_test_summary.json`
- Stage order includes `walk_forward_analysis`.
- `halted: true`.
- Limited core failed because profitable grid rate was `0.06172839506172839`
  versus the required `0.70`.
- WFA was skipped with `skip_reason: prior stage failed`.

## Current Gate Semantics

`src/propstack/research/campaign_stages.py` currently:

- canonicalizes `campaign_tests.stage_order` to include WFA and downstream
  stages;
- runs stages in order;
- sets `halted = True` after the first failed stage unless the caller uses
  `--continue-on-failure`;
- applies the current limited-monkey criteria:
  - random monkey profitable rate >= `0.80`;
  - random monkey median net profit > `0`;
  - trade-path stress enabled;
  - trade-path stress profitable rate >= `0.80`;
  - trade-path stress median net profit > `0`;
  - one-tick-worse trade-path stress profitable;
  - zero Apex/prop-rule violations.

This is stricter than just checking whether the strategy beats randomized
trades on net profit or drawdown.

## Archived Comparison

Archived report inspected:

- `_archived/reports/archive_not_benchmark_20260615/morning_orderflow_momentum/ES/sierra_trade_orderflow_1m_20101229_20260609_full_rth_ny/1m/two_sided_signed_flow_continuation/campaign_tests/campaign_test_summary.json`

Key differences:

- Archived `halted` was `false`, so WFA ran even after limited monkey failed.
- Archived limited monkey criteria were old comparison metrics:
  - `summary.core_beats_monkey_net_profit_rate >= 0.9`;
  - `summary.core_beats_monkey_max_drawdown_rate >= 0.9`;
  - zero Apex violations.
- The archived example failed limited monkey:
  - profitable monkey rate `0.156`;
  - median monkey net `-4153.75`;
  - core beat net-profit rate `0.964`;
  - core beat max-drawdown rate `0.748`.
- Despite that monkey failure, archived WFA executed and passed. That WFA was
  diagnostic under the old run behavior, not comparable to the current
  fail-closed staged methodology.

## Data Window Note

Current canonicalized limited core/monkey data window is not "10% of all data."
It is `first_months: 18` from the configured data range unless a current code
change overrides it. For example, the volume-shock representative run used
actual limited-core data from `2011-01-03 09:30:00-05:00` through
`2012-07-02 15:59:00-04:00`, as recorded in the stage `data_quality`.

Many older active summaries have the actual first/last timestamp in
`stages[].data_quality` but do not have `actual_data_period` backfilled inside
the nested stage `summary` or standalone `core_grid_summary.json`. That is a
reporting clarity issue for old artifacts, not a test-execution issue. Newer
staged code annotates stage summaries before writing them.

## Conclusion

No active variants reached WFA because no active variant passed the current
limited-monkey robustness gate. This is expected under the current methodology
and is materially stricter than archived behavior.

If a future diagnostic WFA is desired for failed monkey variants, it should be
run explicitly with `--continue-on-failure` and labeled non-promotional. Those
results must not be used for tuning, rescue changes, promotion, or candidate
selection.
