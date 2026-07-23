# Staged Gate Correction Audit - 2026-06-17

Decision: NEEDS MANUAL REVIEW for pre-correction core/monkey artifacts; FAIL for
the two corrected-gate reruns that advanced to WFA.

## Problem Found

The staged runner mixed two different monkey-test concepts:

- Random-placebo monkey: should ask whether the strategy beats randomized trade
  paths.
- Actual trade-path stress: should ask whether the strategy itself survives
  worse execution, missed trades, entry delay, time-window jitter, same-bar fill
  ordering, and one-tick-worse slippage.

The previous default limited-monkey criteria incorrectly required the random
monkey distribution itself to be `>=80%` profitable with positive median net
profit. Random trades do not need to be profitable for the placebo test to be
useful; the strategy must beat them. This caused premature monkey failures.

Core grid also had a leniency issue: a stage could pass with `>=70%` profitable
combinations even when zero combinations passed the benchmark checks for trade
count, PF/MAR/expectancy, consecutive losses, and profit concentration.

## Code Changes

Updated `src/propstack/research/campaign_stages.py`:

- `limited_core_grid_test` now also requires
  `summary.number_passing_benchmark >= 1`.
- `limited_monkey_test`, `wfa_oos_monkey_test`, and
  `simulated_incubation_monkey` now use:
  - `summary.core_beats_monkey_net_profit_rate >= 0.90`;
  - `summary.core_beats_monkey_max_drawdown_rate >= 0.90`;
  - actual `trade_path_stress` profitability rate `>=0.80`;
  - actual `trade_path_stress` median net profit `>0`;
  - actual one-tick-worse stress profitable;
  - zero prop-rule violations.
- Limited monkey parameter handoff now prefers profitable benchmark-passing core
  grid rows when `benchmark_passed` is present.

## Active Artifact Impact

Scan scope: active `backtest-campaigns/**/campaign_test_summary.json`, excluding
`_archived`.

- 27 prior core-stage passes are invalid under the corrected core gate because
  they had `number_passing_benchmark = 0`.
- 2 prior limited-monkey failures were valid to advance under the corrected
  monkey gate and were rerun without changing mechanics or parameter space.

Corrected-gate reruns:

| Campaign | Variant/run | Corrected result |
| --- | --- | --- |
| `es_volatility_managed_intraday_premium` | `low_10d_range_midmorning_long_1030/ES/rescue1` | Passed tightened core and corrected monkey; failed WFA early exit because selected first-window IS PF was `0.87 < 1.00`. |
| `es_cboe_put_call_sentiment_intraday` | `falling_total_pc_long_1130/ES/rescue1` | Passed tightened core and corrected monkey; failed WFA early exit because selected first-window IS PF was `0.99 < 1.00`. |

Neither rerun reached WFA OOS monkey, Monte Carlo, simulated incubation, frozen
validation, or candidate reporting.

## Verification

- `python3 -m pytest tests/test_campaign_stages.py` -> PASS, 34 tests.
- `python3 -m pytest tests/test_monkey.py tests/test_core_grid.py` -> PASS, 12 tests.
- Variant JSON summaries validated with `python3 -m json.tool` after reruns.
- Campaign aggregate summaries updated:
  - `backtest-campaigns/es_volatility_managed_intraday_premium/campaign_test_summary.json`
  - `backtest-campaigns/es_cboe_put_call_sentiment_intraday/campaign_test_summary.json`

No paid data was downloaded. No strategy mechanics, signal definitions, or
parameter spaces were changed for the corrected-gate reruns.

