# ES/MES Micro Flow Divergence - Morning Sell Pressure Long Rescue 1

Date: 2026-06-15

Campaign: `es_mes_micro_flow_divergence_reversion`

Variant: `morning_mes_sell_pressure_reversion_long`

Decision: FAIL

## Rescue Scope

This is the one allowed rescue for the failed variant under the clarified
per-failed-variant rescue policy.

Changed:

- `entry.params.flow_threshold` grid from `[0.01, 0.02, 0.03, 0.04]` to
  `[0.005, 0.01, 0.015, 0.02]`.

Unchanged:

- Entry module: `trade_orderflow_pressure`.
- Setup mode: `morning_mes_sell_pressure_reversion_long`.
- Signal time: `10:00:00` America/New_York, using only completed
  `09:30-09:59` bars.
- Direction: long-only ES fade of completed ES/MES 30-minute flow divergence.
- Timeframe, data window, costs, stop module, target module, flatten rule, and
  validation gates.

Config:
`campaigns/es_mes_micro_flow_divergence_reversion/rescue_attempts/parameter_space_rescue_1/morning_mes_sell_pressure_reversion_long/config.yaml`

Report:
`backtest-campaigns/es_mes_micro_flow_divergence_reversion/morning_mes_sell_pressure_reversion_long/ES/rescue1/campaign_test_summary.json`

## Results

Terminal stage: `limited_monkey_test`

Core grid:

- Profitable combinations: `36/36`.
- Profitable-combo rate: `1.0`.
- Apex rule violations: `0`.
- Top-row net profit: `$17,377.50`.
- Top-row profit factor: `1.757849978194505`.
- Top-row MAR: `2.8817376190547774`.

Limited monkey:

- Random-placebo profitable rate: `0.47`.
- Random-placebo median net profit: `-$800.00`.
- Actual trade-path stress profitable rate: `0.9966666666666667`.
- Actual trade-path stress median net profit: `$8,373.41512638981`.
- One-tick-worse net profit: `$6,807.50`.
- One-tick-worse profit factor: `1.1179809358752166`.

Selected core parameters:

- `entry.params.flow_threshold: 0.005`.
- `sl.params.stop_pct: 0.006`.
- `tp.params.target_r_multiple: 1.0`.

## Interpretation

The rescue improved the core surface to `36/36` profitable combinations and
survived actual trade-path perturbation, but the random-placebo monkey
profitability and median-net gates still failed. The variant has now consumed
its one allowed rescue. No second rescue is permitted without changing the
methodology.
