# ES/MES Micro-Flow Divergence Afternoon Sell-Pressure Rescue Attempt 1

Date: 2026-06-15

Decision: FAIL

## Scope

Campaign: `es_mes_micro_flow_divergence_reversion`

Rescued variant: `afternoon_mes_large20_sell_pressure_long`

Config:
`campaigns/es_mes_micro_flow_divergence_reversion/rescue_attempts/parameter_space_rescue_1/afternoon_mes_large20_sell_pressure_long/config.yaml`

Report:
`backtest-campaigns/es_mes_micro_flow_divergence_reversion/afternoon_mes_large20_sell_pressure_long/ES/rescue1/campaign_test_summary.json`

## Rescue Rule

This rescue was allowed because the user clarified that each failed variant can
be rescued once. It changed only existing tunable parameter space. It did not
change:

- entry module: `trade_orderflow_pressure`
- setup mode: `afternoon_mes_large20_sell_pressure_long`
- signal timestamp: `14:00:00`
- signal source: completed `13:55` through `13:59` ES/MES large-20 flow bars
- direction: long-only ES fade of MES sell pressure
- stop module: `percent_from_entry`
- target module: `fixed_r`
- timeframe: `1m`
- data window
- costs, fill assumptions, prop rules, or stage criteria

## Predeclared Rescue Change

The original variant failed core by one combination: `25/36` profitable
combinations, profitable-combo rate `0.6944444444444444`, below the required
`0.70`. The rescue tested the same mechanic in a denser adjacent threshold
neighborhood:

- grid `entry.params.flow_threshold`: `[0.075, 0.1, 0.125, 0.15]`
- grid `sl.params.stop_pct`: `[0.0025, 0.004, 0.006]`
- grid `tp.params.target_r_multiple`: `[1.0, 2.0, 3.0]`

Total combinations: `36`.

## Result

Terminal stage: `limited_monkey_test`.

Core grid:

- `32/36` combinations profitable.
- Profitable-combo rate: `0.8888888888888888`.
- Apex rule-violating iterations: `0`.
- Top row net profit: `$6,712.50`.
- Top row PF: `1.2809`.
- Top row MAR: `1.4675`.
- Top row trades: `100`.
- Top row trades per year: `102.29281698112108`.

Selected monkey row:

- Params: `flow_threshold=0.1`, `stop_pct=0.004`,
  `target_r_multiple=2.0`.
- Core row: `94` trades, net `$3,155.00`, PF `1.1180`, MAR `0.6046`,
  expectancy `0.0255R`, zero Apex violations.

Monkey:

- Random-placebo profitable rate: `0.43`, below `0.80`.
- Median net profit: `-$1,723.75`, below the positive-median requirement.

Actual trade-path stress:

- Profitable rate: `0.4866666666666667`, below `0.80`.
- Median net profit: `-$73.21`, below the positive-median requirement.
- One-tick-worse net profit: `-$532.50`.
- Apex rule-violating iterations: `0`.

## Interpretation

The rescue repaired the original core-surface failure but failed both required
monkey robustness dimensions. Randomized comparable paths were usually
unprofitable, and actual-trade perturbations did not survive missed trades,
entry delays, time-window jitter, and one-tick worse slippage.

The branch did not earn WFA, WFA OOS monkey, Monte Carlo, or frozen acceptance.
No further rescue attempt is permitted for this variant.
