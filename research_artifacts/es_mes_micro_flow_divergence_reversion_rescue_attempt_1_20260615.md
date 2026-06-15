# ES/MES Micro-Flow Divergence Reversion Rescue Attempt 1

Date: 2026-06-15

Decision: FAIL

## Scope

Campaign: `es_mes_micro_flow_divergence_reversion`

Rescued variant: `midday_mes_price_richness_fade`

Config:
`campaigns/es_mes_micro_flow_divergence_reversion/rescue_attempts/parameter_space_rescue_1/midday_mes_price_richness_fade/config.yaml`

Report:
`backtest-campaigns/es_mes_micro_flow_divergence_reversion/midday_mes_price_richness_fade/ES/rescue1/campaign_test_summary.json`

## Rescue Rule

This rescue was originally allowed after all five campaign variants failed; the
current clarified policy allows one rescue per failed variant. It changed only
existing tunable parameter space. It did not change:

- entry module: `trade_orderflow_pressure`
- setup mode: `midday_mes_price_richness_fade`
- signal timestamp: `11:00:00`
- signal source: completed `10:57` through `10:59` ES/MES return-richness bars
- direction logic: two-sided ES fade of MES-minus-ES richness
- stop module: `percent_from_entry`
- target module: `fixed_r`
- timeframe: `1m`
- data window
- costs, fill assumptions, prop rules, or stage criteria

## Predeclared Rescue Change

The original variant had the strongest local economics and enough trade density
inside this one-year ES/MES local cache, but failed the core surface robustness
gate with `24/36` profitable combinations. The rescue tested the same mechanic
with a lower existing flow-threshold neighborhood:

- grid `entry.params.flow_threshold`: `[0.25, 0.5, 0.75, 1.0]`
- grid `sl.params.stop_pct`: `[0.0025, 0.004, 0.006]`
- grid `tp.params.target_r_multiple`: `[1.0, 2.0, 3.0]`

Total combinations: `36`.

## Result

Terminal stage: `limited_monkey_test`.

Core grid:

- `36/36` combinations profitable.
- Profitable-combo rate: `1.0`.
- Apex rule-violating iterations: `0`.
- Top row net profit: `$44,752.50`.
- Top row PF: `1.9508`.
- Top row MAR: `8.9576`.
- Top row trades: `132`.
- Top row trades per year: `133.915183686381`.

Selected monkey row:

- Params: `flow_threshold=0.25`, `stop_pct=0.006`,
  `target_r_multiple=1.0`.
- Core row: `132` trades, net `$32,452.50`, PF `1.6458`, MAR `4.2800`,
  expectancy `0.1265R`, zero Apex violations.

Monkey:

- Random-placebo profitable rate: `0.38666666666666666`, below `0.80`.
- Median net profit: `-$5,822.50`, below the positive-median requirement.
- Core beat monkey net profit rate: `0.9866666666666667`.
- Core beat monkey max drawdown rate: `0.96`.

Actual trade-path stress:

- Profitable rate: `1.0`.
- Median net profit: `$29,551.94`.
- One-tick-worse net profit: `$28,827.50`.
- Apex rule-violating iterations: `0`.

## Interpretation

The rescue repaired the original core-surface failure but did not survive the
random-placebo monkey gate. The exact trade path is resilient to missed trades,
one-bar entry delay, one-tick worse slippage, and time-window jitter, but the
strategy does not pass the methodology because randomized comparable paths are
usually not profitable and have negative median net PnL.

The branch did not earn WFA, WFA OOS monkey, Monte Carlo, or frozen acceptance.
No further rescue attempt is permitted for this variant under the current
methodology.
