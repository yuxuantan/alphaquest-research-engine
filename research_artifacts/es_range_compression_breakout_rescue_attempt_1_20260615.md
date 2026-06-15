# ES Range-Compression Breakout Rescue Attempt 1

Date: 2026-06-15

Decision: FAIL

## Scope

Campaign: `es_range_compression_breakout`

Rescued variant: `id_nr4_prior_session_breakout`

Config:
`campaigns/es_range_compression_breakout/rescue_attempts/parameter_space_rescue_1/id_nr4_prior_session_breakout/config.yaml`

Report:
`backtest-campaigns/es_range_compression_breakout/id_nr4_prior_session_breakout/ES/rescue1/campaign_test_summary.json`

## Rescue Rule

This rescue was originally allowed after all five campaign variants failed; the
current clarified policy allows one rescue per failed variant. It changed only
existing fixed strategy parameters and the declared tunable parameter space. It
did not change:

- entry module: `range_compression_breakout`
- setup mode: `id_nr4_prior_session_breakout`
- breakout level source: `prior_session`
- stop module: `percent_from_entry`
- target module: `fixed_r`
- timeframe: `5m`
- data window
- costs, fill assumptions, prop rules, or stage criteria

## Predeclared Rescue Change

The original ID/NR4 run passed core but failed monkey with sparse trade count and
negative random-placebo median PnL. The rescue broadened existing parameters to
test whether the same ID/NR4 prior-session breakout mechanic had enough density:

- fixed `strategy.entry.params.end_time`: `14:00:00` to `15:00:00`
- fixed `strategy.entry.params.max_prior_range_points`: `70` to `130`
- grid `entry.params.min_breakout_ticks`: `[0, 1, 2]`
- grid `entry.params.max_prior_range_points`: `[100, 130, 160]`
- grid `sl.params.stop_pct`: `[0.0025, 0.004, 0.006]`
- grid `tp.params.target_r_multiple`: `[1.0, 1.5, 2.0]`

Total combinations: `81`.

## Result

Terminal stage: `limited_monkey_test`.

Core grid:

- `81/81` combinations profitable.
- Profitable-combo rate: `1.0`.
- Apex rule-violating iterations: `0`.
- Top rows remained sparse: top `total_trades=19`,
  `trades_per_year=13.14424385912992`.

Selected monkey row:

- Params: `min_breakout_ticks=0`, `max_prior_range_points=100`,
  `stop_pct=0.0025`, `target_r_multiple=1.5`.
- Core row: `19` trades, net `$1,167.50`, PF `1.8038`, MAR `1.6184`,
  expectancy `0.3727R`, zero Apex violations.

Monkey:

- Random-placebo profitable rate: `0.2866666666666667`, below `0.80`.
- Median net profit: `-$548.75`, below the positive-median requirement.
- Core beat monkey net profit rate: `0.9633333333333334`.
- Core beat monkey max drawdown rate: `0.9066666666666666`.

Actual trade-path stress:

- Profitable rate: `0.98`.
- Median net profit: `$333.21`.
- One-tick-worse net profit: `$692.50`.
- Apex rule-violating iterations: `0`.

## Interpretation

The rescue did not repair the original failure mode. The exact trades survive
one-tick worse slippage and actual-trade perturbations, but the strategy remains
too sparse and does not beat the random-placebo profitability/median gate. It
did not earn WFA.

No further rescue attempt is permitted for this variant under the current
methodology.
