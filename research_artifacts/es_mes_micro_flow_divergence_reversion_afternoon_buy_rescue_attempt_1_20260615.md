# ES/MES Micro Flow Divergence - Afternoon Buy Pressure Short Rescue 1

Date: 2026-06-15

Campaign: `es_mes_micro_flow_divergence_reversion`

Variant: `afternoon_mes_large20_buy_pressure_short`

Decision: FAIL

## Rescue Scope

This is the one allowed rescue for the failed variant under the clarified
per-failed-variant rescue policy.

Changed:

- `entry.params.flow_threshold` grid from `[0.1, 0.125, 0.15, 0.175]` to
  `[0.075, 0.1, 0.125, 0.15]`.

Unchanged:

- Entry module: `trade_orderflow_pressure`.
- Setup mode: `afternoon_mes_large20_buy_pressure_short`.
- Signal time: `14:00:00` America/New_York, using only completed
  `13:55-13:59` bars.
- Direction: short-only ES fade of completed MES large-20 buy pressure without
  ES follow-through.
- Timeframe, data window, costs, stop module, target module, flatten rule, and
  validation gates.

Config:
`campaigns/es_mes_micro_flow_divergence_reversion/rescue_attempts/parameter_space_rescue_1/afternoon_mes_large20_buy_pressure_short/config.yaml`

Report:
`backtest-campaigns/es_mes_micro_flow_divergence_reversion/afternoon_mes_large20_buy_pressure_short/ES/rescue1/campaign_test_summary.json`

## Results

Terminal stage: `limited_monkey_test`

Core grid:

- Profitable combinations: `36/36`.
- Profitable-combo rate: `1.0`.
- Apex rule violations: `0`.
- Top-row net profit: `$13,805.00`.
- Top-row profit factor: `2.1999130812690133`.
- Top-row MAR: `6.002633880079931`.

Limited monkey:

- Random-placebo profitable rate: `0.36666666666666664`.
- Random-placebo median net profit: `-$1,901.25`.
- Actual trade-path stress profitable rate: `1.0`.
- Actual trade-path stress median net profit: `$10,734.011995680594`.
- One-tick-worse net profit: `$10,292.50`.
- One-tick-worse profit factor: `1.9516874711049468`.

Selected core parameters:

- `entry.params.flow_threshold: 0.125`.
- `sl.params.stop_pct: 0.004`.
- `tp.params.target_r_multiple: 2.0`.

## Interpretation

The rescue preserved the strong core-grid behaviour and actual trade-path stress
survival, but it still failed the required random-placebo monkey profitability
and median-net gates. The variant has now consumed its one allowed rescue. No
second rescue is permitted without changing the methodology.
