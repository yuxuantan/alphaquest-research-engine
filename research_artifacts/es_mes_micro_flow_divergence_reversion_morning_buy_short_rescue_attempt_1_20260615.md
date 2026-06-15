# ES/MES Micro-Flow Divergence Morning Buy-Pressure Short Rescue Attempt 1

Date: 2026-06-15

Decision: FAIL

## Scope

Campaign: `es_mes_micro_flow_divergence_reversion`

Rescued variant: `morning_mes_buy_pressure_reversion_short`

Config:
`campaigns/es_mes_micro_flow_divergence_reversion/rescue_attempts/parameter_space_rescue_1/morning_mes_buy_pressure_reversion_short/config.yaml`

Report:
`backtest-campaigns/es_mes_micro_flow_divergence_reversion/morning_mes_buy_pressure_reversion_short/ES/rescue1/campaign_test_summary.json`

## Rescue Rule

This rescue was allowed because each failed variant can be rescued once. It
changed only existing tunable parameter space. It did not change:

- entry module: `trade_orderflow_pressure`
- setup mode: `morning_mes_buy_pressure_reversion_short`
- signal timestamp: `10:00:00`
- signal source: completed `09:30` through `09:59` ES/MES imbalance bars
- direction: short-only ES fade of MES buy-pressure divergence
- stop module: `percent_from_entry`
- target module: `fixed_r`
- timeframe: `1m`
- data window
- costs, fill assumptions, prop rules, or stage criteria

## Predeclared Rescue Change

The original variant failed core with `24/36` profitable combinations,
profitable-combo rate `0.6666666666666666`, below the required `0.70`. The
rescue tested the same mechanic in a denser adjacent lower threshold
neighborhood:

- grid `entry.params.flow_threshold`: `[0.005, 0.01, 0.015, 0.02]`
- grid `sl.params.stop_pct`: `[0.0025, 0.004, 0.006]`
- grid `tp.params.target_r_multiple`: `[1.0, 2.0, 3.0]`

Total combinations: `36`.

## Result

Terminal stage: `limited_monkey_test`.

Core grid:

- `36/36` combinations profitable.
- Profitable-combo rate: `1.0`.
- Apex rule-violating iterations: `0`.
- Top row net profit: `$11,412.50`.
- Top row PF: `1.4327`.
- Top row MAR: `1.4006`.
- Top row trades: `80`.
- Top row trades per year: `81.3784326884582`.

Selected monkey row:

- Params: `flow_threshold=0.015`, `stop_pct=0.0025`,
  `target_r_multiple=3.0`.
- Core row: `49` trades, net `$5,892.50`, PF `1.4039`, MAR `1.4768`,
  expectancy `0.1486R`, zero Apex violations.

Monkey:

- Random-placebo profitable rate: `0.36`, below `0.80`.
- Median net profit: `-$2,702.50`, below the positive-median requirement.

Actual trade-path stress:

- Profitable rate: `0.9966666666666667`.
- Median net profit: `$4,958.30`.
- One-tick-worse net profit: `$4,467.50`.
- Apex rule-violating iterations: `0`.

## Interpretation

The rescue repaired the original core-surface failure, and the exact trade path
survived actual-trade perturbations and one-tick worse slippage. It still failed
the required random-placebo monkey gate. Comparable randomized paths were mostly
unprofitable, so the branch did not earn WFA.

No further rescue attempt is permitted for this variant.
