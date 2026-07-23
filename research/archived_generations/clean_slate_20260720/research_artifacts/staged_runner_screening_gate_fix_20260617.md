# Staged Runner Screening Gate Fix - 2026-06-17

Purpose: remove a false-negative risk found while comparing current staged
tests to archived runs, without weakening the final methodology.

## Changes

- Run-level `config.yaml` is now the effective canonical config actually used
  by the staged runner.
- The original input config is retained beside it as `source_config.yaml`.
- Run summaries now include `effective_config_path`,
  `source_config_snapshot_path`, and both effective/source config hashes.
- Limited core-grid benchmark pass counting now uses a screening benchmark:
  trade-density, drawdown/concentration, and rule-compliance thresholds are
  retained; full-stage PF/MAR/expectancy gates are left for WFA and later
  stages.
- Full-span absolute trade-count requirements are scaled to the limited screen
  period. Example: a 50 trades/year rule over an 18-month screen requires about
  75-76 trades, not a full-history 500-trade absolute count.
- Monkey pass/fail now follows the stated methodology: the gate is the stressed
  actual trade path, not a separate random-placebo comparison. The random
  monkey output is still reported for diagnostics.

## Effective Limited Core-Grid Gate

- valid parameter-combination count: exactly 1 fixed combo or 8-120 tunable
  combos
- at least 70% profitable iterations after costs
- at least one screening-benchmark-passing parameter set
- no Apex/flatten rule violations

The screening benchmark records its active thresholds in
`limited_core_grid_test/core_grid_summary.json` under:

- `benchmark_thresholds`
- `benchmark_threshold_adjustments`

## Effective Monkey Gate

- actual trade-path stress enabled
- stressed trade paths at least 80% profitable
- stressed trade-path median net profit positive
- one-tick-worse slippage path still profitable
- no Apex/flatten rule violations

Stress mechanics remain:

- entry delay
- missed trades
- worse slippage
- time-window trim/jitter
- pessimistic same-bar stop/target ordering

## Verification

- `python3 -m pytest tests/test_campaign_stages.py -q` passed: 34 tests.
- `python3 -m pytest tests/test_campaign_stages.py tests/test_backtest_engine.py tests/test_preflight.py tests/test_wfa.py -q` passed: 96 tests.
- `python3 -m pytest tests/test_monkey.py tests/test_core_grid.py -q` passed: 12 tests.
- `python3 -m py_compile src/propstack/research/campaign_stages.py src/propstack/research/core_grid.py src/propstack/research/monkey.py` passed.
