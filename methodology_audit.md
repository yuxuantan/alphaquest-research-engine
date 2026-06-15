# Futures Backtest Methodology Audit

Audit date: 2026-06-15

Overall status: FAIL

Reason: the engine/preflight path now passes focused sanity checks, but no ES strategy candidate in the active search passed the corrected staged methodology. The active ES/MES micro-flow divergence, ES prior-session IBS, ES Connors RSI2, ES range-compression breakout, ES RTH intraday risk premium, ES overnight-intraday reversal, and ES signed-orderflow persistence campaigns all failed before WFA under the corrected objective gates. The completed parameter-only rescue attempts also failed before WFA.

## Engine And Methodology Fixes

- Point value handling: `BacktestEngine`, monkey trade-log construction, and Monte Carlo prop-rule sizing now derive `tick_value` from `core.point_value * core.tick_size` when `core.tick_value` is absent. This closes the preflight/engine mismatch where non-ES configs could be accepted but valued with ES's default tick value.
- Monkey gate: staged campaign criteria now require `summary.percentage_profitable >= 0.80` and `summary.median_net_profit > 0` for limited monkey, WFA OOS monkey, and incubation monkey. The previous proxy only checked whether the core run beat randomized paths.
- Actual trade-path stress: monkey stages now also write `trade_path_stress_results.csv` / `trade_path_stress_summary.json` and require actual strategy trades to survive missed trades, one-bar entry delays, one-tick worse slippage, time-window trims, stop-first same-bar fill ordering, and prop-rule checks.
- WFA gate: staged WFA now checks `stitched_oos_metrics.trades_per_year >= 50` and `stitched_oos_metrics.expectancy_r > 0`, matching the research rule's per-year trade-density and positive-expectancy requirements.
- Acceptance gate: frozen acceptance now requires positive `metrics.expectancy_r` in addition to PF, MAR, trade count, and Apex-rule compliance.
- Shortlist data window: limited core/monkey stages now use a deterministic contiguous first-window sample instead of a seeded random-month sample.
- Connors RSI2 preflight: `BacktestEngine` now warns when `connors_rsi2_mean_reversion` requests a VWAP trend/extension filter but the prepared data lacks `vwap`.
- Fixed-combo handling: staged core-grid criteria now accept exactly one combination only when the strategy declares no tunable parameters; tunable grids still must stay in the 8 to 120 combination range.
- Variants index hardening: campaign variant metadata updates now use a lock-protected atomic writer, preventing concurrent staged runs from corrupting `variants_index.yaml`.
- Overnight reversal preflight: `BacktestEngine` now warns when `overnight_intraday_reversal` is run without the prior-RTH close feature required to compute the close-to-open gap.

## Verified Controls

- Bar-close signals enter no earlier than the next bar open.
- Same-bar stop/target conflicts fall back to stop-first pessimistic handling when no detail data resolves order.
- Commission, slippage, tick size, point value, and tick value are explicit and tested.
- Apex/prop-style forced flatten, latest-entry, no-overnight, and pending-order cancellation diagnostics are config driven.
- Preflight fails closed on missing timezone, duplicate bars, missing forced-flatten config, parameter-count violations, and excessive parameter combinations.
- Rescue governance now scopes rescues to a failed variant: each failed variant can use at most one logged rescue, and rescues may change only existing fixed parameters or tunable parameter space inside existing modules.

## Campaign Results

### `es_mes_micro_flow_divergence_reversion`

Source thesis: ES may mean-revert when completed MES flow or short-horizon MES price movement diverges from ES.

Data: local one-year ES/MES caches from `2025-06-10` through `2026-06-08`.

| Variant | Terminal stage | Failure | Actual-trade stress |
| --- | --- | --- | --- |
| `afternoon_mes_large20_buy_pressure_short` | `limited_monkey_test` | random monkey `percentage_profitable=0.38`, `median_net_profit=-2552.5` | passed stress gate: `percentage_profitable=1.0`, one-tick net `9992.5` |
| `afternoon_mes_large20_sell_pressure_long` | `limited_core_grid_test` | `percentage_profitable_iterations=0.6944444444444444` | not reached |
| `midday_mes_price_richness_fade` | `limited_core_grid_test` | `percentage_profitable_iterations=0.6666666666666666` | not reached |
| `morning_mes_buy_pressure_reversion_short` | `limited_core_grid_test` | `percentage_profitable_iterations=0.6666666666666666` | not reached |
| `morning_mes_sell_pressure_reversion_long` | `limited_monkey_test` | random monkey `percentage_profitable=0.44`, `median_net_profit=-1335.0` | passed stress gate: `percentage_profitable=0.99`, one-tick net `6430.0` |

Decision: FAIL. No variant reached WFA under the corrected monkey/core gates.

Rescue attempt 1: FAIL. The rescue was originally allowed after all five
original variants failed; under the clarified current rule it consumes this
failed variant's one rescue. It changed only existing tunable parameter space for
`midday_mes_price_richness_fade`; it did not change modules, setup mode,
direction logic, signal timestamp, timeframe, data window, costs, or stage
criteria. Report:
`backtest-campaigns/es_mes_micro_flow_divergence_reversion/midday_mes_price_richness_fade/ES/rescue1/campaign_test_summary.json`.
Core passed with `36/36` profitable combinations and zero Apex violations, but
limited monkey failed with random-placebo `percentage_profitable=0.38666666666666666`
and `median_net_profit=-5822.5`. Actual trade-path stress passed with
`percentage_profitable=1.0` and one-tick-worse net profit `$28,827.50`, but the
required random-placebo profitability/median gate failed. Audit:
`research_artifacts/es_mes_micro_flow_divergence_reversion_rescue_attempt_1_20260615.md`.

Rescue attempt 1 for `afternoon_mes_large20_sell_pressure_long`: FAIL. This
rescue was allowed under the clarified per-failed-variant rule and changed only
the existing `flow_threshold` grid. It did not change modules, setup mode,
signal time, direction, timeframe, data window, costs, or stage criteria.
Report:
`backtest-campaigns/es_mes_micro_flow_divergence_reversion/afternoon_mes_large20_sell_pressure_long/ES/rescue1/campaign_test_summary.json`.
Core passed with `32/36` profitable combinations and zero Apex violations, but
limited monkey failed with random-placebo `percentage_profitable=0.43` and
`median_net_profit=-1723.75`. Actual trade-path stress also failed with
`percentage_profitable=0.4866666666666667` and one-tick-worse net profit
`-$532.50`. Audit:
`research_artifacts/es_mes_micro_flow_divergence_reversion_afternoon_sell_rescue_attempt_1_20260615.md`.

Rescue attempt 1 for `morning_mes_buy_pressure_reversion_short`: FAIL. This
rescue was allowed under the clarified per-failed-variant rule and changed only
the existing `flow_threshold` grid. It did not change modules, setup mode,
signal time, direction, timeframe, data window, costs, or stage criteria.
Report:
`backtest-campaigns/es_mes_micro_flow_divergence_reversion/morning_mes_buy_pressure_reversion_short/ES/rescue1/campaign_test_summary.json`.
Core passed with `36/36` profitable combinations and zero Apex violations, but
limited monkey failed with random-placebo `percentage_profitable=0.36` and
`median_net_profit=-2702.5`. Actual trade-path stress passed with
`percentage_profitable=0.9966666666666667` and one-tick-worse net profit
`$4,467.50`, but the required random-placebo profitability/median gate failed.
Audit:
`research_artifacts/es_mes_micro_flow_divergence_reversion_morning_buy_short_rescue_attempt_1_20260615.md`.

Rescue attempt 1 for `afternoon_mes_large20_buy_pressure_short`: FAIL. This
rescue was allowed under the clarified per-failed-variant rule and changed only
the existing `flow_threshold` grid. It did not change modules, setup mode,
signal time, direction, timeframe, data window, costs, or stage criteria.
Report:
`backtest-campaigns/es_mes_micro_flow_divergence_reversion/afternoon_mes_large20_buy_pressure_short/ES/rescue1/campaign_test_summary.json`.
Core passed with `36/36` profitable combinations and zero Apex violations, but
limited monkey failed with random-placebo `percentage_profitable=0.36666666666666664`
and `median_net_profit=-1901.25`. Actual trade-path stress passed with
`percentage_profitable=1.0` and one-tick-worse net profit `$10,292.50`, but the
required random-placebo profitability/median gate failed. Audit:
`research_artifacts/es_mes_micro_flow_divergence_reversion_afternoon_buy_rescue_attempt_1_20260615.md`.

Rescue attempt 1 for `morning_mes_sell_pressure_reversion_long`: FAIL. This
rescue was allowed under the clarified per-failed-variant rule and changed only
the existing `flow_threshold` grid. It did not change modules, setup mode,
signal time, direction, timeframe, data window, costs, or stage criteria.
Report:
`backtest-campaigns/es_mes_micro_flow_divergence_reversion/morning_mes_sell_pressure_reversion_long/ES/rescue1/campaign_test_summary.json`.
Core passed with `36/36` profitable combinations and zero Apex violations, but
limited monkey failed with random-placebo `percentage_profitable=0.47` and
`median_net_profit=-800.0`. Actual trade-path stress passed with
`percentage_profitable=0.9966666666666667` and one-tick-worse net profit
`$6,807.50`, but the required random-placebo profitability/median gate failed.
Audit:
`research_artifacts/es_mes_micro_flow_divergence_reversion_morning_sell_rescue_attempt_1_20260615.md`.

### `es_prior_session_ibs_reversion`

Source thesis: prior-session Internal Bar Strength may mean-revert in equity-index futures during the next RTH session.

Data: local ES Sierra RTH cache from `2011-01-03` through `2026-06-09`.

Note: the first `run1` open-variant artifacts were invalidated because the configs did not request the prior-RTH feature set and produced zero trades. Corrected `run2` configs used `feature_set: pdh_pdl_sweep`; the zero-trade artifacts were retained for audit.

| Variant | Terminal stage | Profitable combo rate | Top net / trades | Decision |
| --- | --- | ---: | ---: | --- |
| `open_low_ibs_long` | `limited_core_grid_test` | `0.0` | `-1170.0` / `19` | FAIL |
| `open_high_ibs_short` | `limited_core_grid_test` | `0.3333333333333333` | `1060.0` / `53` | FAIL |
| `open_two_sided_ibs_reversion` | `limited_core_grid_test` | `0.0` | `-1490.0` / `83` | FAIL |
| `delayed_low_ibs_long_range_filtered` | `limited_core_grid_test` | `0.3148148148148148` | `1315.0` / `42` | FAIL |
| `delayed_high_ibs_short_range_filtered` | `limited_core_grid_test` | `0.2037037037037037` | `1835.0` / `53` | FAIL |

Decision: FAIL. Best corrected profitable-combo rate was `0.3333333333333333`, below the required `0.70`.

### `es_connors_rsi2_mean_reversion`

Source thesis: Connors-style RSI2 extremes may mean-revert in liquid equity-index futures when filtered by intraday trend or VWAP context.

Data: local ES Sierra RTH cache from `2011-01-03` through `2026-06-09`.

| Variant | Terminal stage | Profitable combo rate | Top net / trades | Decision |
| --- | --- | ---: | ---: | --- |
| `five_min_long_vwap_extreme_1430` | `limited_core_grid_test` | `0.04938271604938271` | `427.5` / `87` | FAIL |
| `five_min_short_vwap_extreme_1430` | `limited_core_grid_test` | `0.0` | `-1235.0` / `117` | FAIL |
| `fifteen_min_long_uptrend_pullback_1545` | `limited_core_grid_test` | `0.06172839506172839` | `2646.25` / `92` | FAIL |
| `fifteen_min_short_downtrend_bounce_1545` | `limited_core_grid_test` | `0.0` | `-1302.5` / `133` | FAIL |
| `thirty_min_two_sided_trend_reversion_1530` | `limited_core_grid_test` | `0.037037037037037035` | `1207.5` / `101` | FAIL |

Decision: FAIL. Best profitable-combo rate was `0.06172839506172839`, below the required `0.70`.

### `es_range_compression_breakout`

Source thesis: NR4, ID/NR4, and NR7 compression patterns may precede intraday volatility expansion and same-session breakout continuation.

Data: local ES Sierra RTH cache from `2011-01-03` through `2026-06-09`.

Signal-density sanity check before testing: all five variants emitted nonzero signals across all 16 calendar years in the configured data window, so the run was not a zero-signal data wiring failure.

| Variant | Terminal stage | Core profitable combo rate | Top net / trades | Monkey result | Decision |
| --- | --- | ---: | ---: | --- | --- |
| `nr4_prior_session_breakout` | `limited_core_grid_test` | `0.5802469135802469` | `2752.5` / `107` | not reached | FAIL |
| `id_nr4_prior_session_breakout` | `limited_monkey_test` | `1.0` | `1785.0` / `18` | random monkey `percentage_profitable=0.3933333333333333`, `median_net_profit=-570.0`; actual-trade stress passed with `percentage_profitable=0.9533333333333334`, one-tick net `1285.0` | FAIL |
| `nr7_opening_range_30_breakout` | `limited_core_grid_test` | `0.037037037037037035` | `95.0` / `61` | not reached | FAIL |
| `nr7_opening_range_15_long_breakout` | `limited_core_grid_test` | `0.5555555555555556` | `1382.5` / `41` | not reached | FAIL |
| `nr7_opening_range_15_short_breakout` | `limited_core_grid_test` | `0.0` | `-882.5` / `34` | not reached | FAIL |

Decision: FAIL. Four variants failed the `0.70` core profitable-combo gate. The ID/NR4 variant passed core but had only `18` trades in the selected core row and failed the random-placebo monkey gate with negative median PnL, so it did not earn WFA.

Rescue attempt 1: FAIL. The rescue was originally allowed after all five
original variants failed; under the clarified current rule it consumes this
failed variant's one rescue. It changed only existing fixed strategy parameters
plus the tunable parameter grid for `id_nr4_prior_session_breakout`; it did not change
modules, setup mode, timeframe, data window, costs, or stage criteria. Report:
`backtest-campaigns/es_range_compression_breakout/id_nr4_prior_session_breakout/ES/rescue1/campaign_test_summary.json`.
Core passed again with `81/81` profitable combinations, but top rows remained
sparse at `19` trades. Limited monkey failed with random-placebo
`percentage_profitable=0.2866666666666667` and `median_net_profit=-548.75`.
Actual trade-path stress passed with `percentage_profitable=0.98` and
one-tick-worse net profit `$692.50`, but the required random-placebo
profitability/median gate failed. Audit:
`research_artifacts/es_range_compression_breakout_rescue_attempt_1_20260615.md`.

### `es_rth_intraday_risk_premium`

Source thesis: equity-index futures may retain a positive RTH intraday premium after a completed early-session bar.

Data: local ES Sierra RTH cache from `2011-01-03` through `2026-06-09`.

Signal-density sanity check before testing: all five fixed-time variants emitted `3817` baseline signals across the configured data window, so the run was not a zero-signal data wiring failure.

| Variant | Terminal stage | Fixed combo net | PF | Trades | Expectancy R | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `open_0935_long` | `limited_core_grid_test` | `-16190.0` | `0.7593370247872459` | `363` | `-0.12341172067563005` | FAIL |
| `first_hour_1000_long` | `limited_core_grid_test` | `-15315.0` | `0.7575589678644926` | `363` | `-0.11573397095390234` | FAIL |
| `midmorning_1030_long` | `limited_core_grid_test` | `-9327.5` | `0.8405555555555555` | `363` | `-0.06250703361311283` | FAIL |
| `late_morning_1100_long` | `limited_core_grid_test` | `-4777.5` | `0.9108841634023503` | `363` | `-0.025730858511327788` | FAIL |
| `early_afternoon_1300_long` | `limited_core_grid_test` | `-10440.0` | `0.7657354426119152` | `363` | `-0.0741318210488584` | FAIL |

Decision: FAIL. Every fixed-combo long-bias variant lost money after costs. No WFA was earned.

### `es_overnight_intraday_reversal`

Source thesis: overnight gaps may reverse during the following intraday session as liquidity providers are compensated for opening inventory pressure.

Data: local ES Sierra RTH cache from `2011-01-03` through `2026-06-09` with `feature_set: pdh_pdl_sweep` for prior RTH close.

Signal-density sanity check before testing: all five variants produced nonzero baseline trades. Baseline trade counts ranged from `423` to `1161`.

| Variant | Terminal stage | Profitable combo rate | Benchmark pass combos | Top net / trades per year | Top PF / MAR | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `first5_confirm_reversal_1000` | `limited_core_grid_test` | `0.012345679012345678` | `0` | `152.5` / `28.382792844693682` | `1.0286519492719586` / `0.06347638787225555` | FAIL |
| `first15_confirm_reversal_1000` | `limited_core_grid_test` | `0.1728395061728395` | `0` | `1982.5` / `65.3933404996568` | `1.1296387117868236` / `0.3646686603265131` | FAIL |
| `first30_noncontinuation_1000` | `limited_core_grid_test` | `0.024691358024691357` | `0` | `430.0` / `54.0207107707709` | `1.0389845874886672` / `0.12424091766234946` | FAIL |
| `low_overnight_first15_long_1000` | `limited_core_grid_test` | `0.08641975308641975` | `0` | `1147.5` / `39.97127844966522` | `1.152643831060858` / `0.4520801176937031` | FAIL |
| `high_overnight_first15_short_1000` | `limited_core_grid_test` | `0.4074074074074074` | `0` | `3842.5` / `36.92146896327592` | `1.4204048140043763` / `1.4504362709137382` | FAIL |

Decision: FAIL. All variants failed the `0.70` core profitable-combo gate and none produced a benchmark-passing combination. The best single top combo was the short-only variant, but it had only `33/81` profitable combinations and insufficient trades per year.

Rescue attempt 1: FAIL. The rescue was originally allowed after all five
original variants failed; under the clarified current rule it consumes this
failed variant's one rescue. It changed only existing threshold and stop/target
parameter space for `high_overnight_first15_short_1000`; it did not change modules, setup
mode, direction, confirmation-window length, entry time, timeframe, data window,
costs, or stage criteria. Report:
`backtest-campaigns/es_overnight_intraday_reversal/high_overnight_first15_short_1000/ES/rescue1/campaign_test_summary.json`.
Core failed with `56/81` profitable combinations, profitable-combo rate
`0.691358024691358`, zero benchmark-passing combinations, and zero Apex
violations. The top row remained sparse at `54` trades and `36.92146896327592`
trades per year. Audit:
`research_artifacts/es_overnight_intraday_reversal_rescue_attempt_1_20260615.md`.

### `es_signed_orderflow_persistence`

Source thesis: own-ES aggregate signed-orderflow imbalance may persist over
short intraday horizons after completed-bar price confirmation, consistent with
short-horizon order-flow impact, flow toxicity, and persistent order-splitting
research.

Data: corrected local ES Sierra aggregate orderflow cache from `2011-01-03`
through `2026-06-09`.

| Variant | Original profitable combo rate | Original top net / trades | Rescue profitable combo rate | Rescue top net / trades | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `early_5m_signed_flow_continuation_1000` | `0.12345679012345678` | `1447.5` / `198` | `0.1111111111111111` | `728.75` / `198` | FAIL |
| `late_morning_15m_signed_flow_continuation_1130` | `0.07407407407407407` | `612.5` / `65` | `0.012345679012345678` | `90.625` / `70` | FAIL |
| `midday_30m_signed_flow_continuation_1230` | `0.037037037037037035` | `302.5` / `42` | `0.0` | `-3063.75` / `179` | FAIL |
| `afternoon_60m_signed_flow_continuation_1400` | `0.012345679012345678` | `555.0` / `74` | `0.0` | `-1038.75` / `149` | FAIL |
| `late_large20_30m_flow_continuation_1500` | `0.0` | `-156.25` / `35` | `0.0` | `-212.5` / `95` | FAIL |

Decision: FAIL. All five original variants and all five one-time
parameter-space-only rescues failed the `0.70` core profitable-combo gate before
monkey, WFA, Monte Carlo, or frozen validation. Report:
`backtest-campaigns/es_signed_orderflow_persistence/campaign_test_summary.json`.
Audit:
`research_artifacts/es_signed_orderflow_persistence_rescue_attempt_1_20260615.md`.

## Duplicate-Edge Scope

- No local ES `campaign_test_summary.json` currently has `passed=true`.
- Archived tests are ignored when checking whether a proposed campaign is a duplicate edge. They remain historical evidence only and must not block a fresh campaign by themselves.
- The duplicate-edge gate now compares only against active `campaigns/`, active `backtest-campaigns/`, and current non-archived `research_ledger.csv` rows.
- Active rejected edge families from this run remain blocked from relaunch under a new active name: ES/MES micro-flow divergence, prior-session IBS, Connors RSI2, range-compression breakout, RTH intraday risk premium, overnight-intraday reversal, and own-ES signed-orderflow persistence.
- Policy artifact: `research_artifacts/duplicate_edge_scope_policy_20260615.md`.

## Current Data Gate

The retained external-data branches remain data-gated:

- `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short_2020start` requires a longer ES+MES `trades` cache from `2020-01-01` onward. Local cache check found only `data/cache/orderflow/es_mes_flow_divergence_1m_20250610_20260608.csv` and `data/cache/orderflow/es_mes_price_flow_divergence_1m_20250610_20260608.csv`.
- `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim` requires an approved ES `tbbo` pilot cache. Local cache check found no TBBO liquidity cache; only metadata/cost manifests and the pilot protocol are present.

No paid Databento data was pulled in this run.

Durable local-data/no-duplicate audit:
`research_artifacts/local_no_duplicate_data_gate_audit_20260615.md`.

Continuation audit after ES/MES rescue:
`research_artifacts/es_goal_continuation_audit_20260615.md`.

The original blocked/data-gate conclusion in that continuation audit was
temporarily superseded by the user's clarification that each failed variant can
be rescued once. After applying the clarified rule to all active failed
variants, the current fail-closed conclusion is again a data gate.

## Rescue Decision

All 35 active failed ES variants now have exactly one `rescue1` report. The 23
previously unrescued variants were given parameter-only rescue runs after the
user clarified that each failed variant can be rescued once. Existing `rescue1`
reports were not rerun, and no second rescue was created for any variant. The
later `es_signed_orderflow_persistence` campaign added five more failed variants
and five completed `rescue1` runs.

Every rescue failed before WFA or at `limited_monkey_test`. The strongest
remaining surfaces still failed objective gates: the best new IBS rescue reached
only `0.5061728395061729` profitable core combinations, the best new Connors
RSI2 rescue reached `0.345679012345679`, the best new range-compression rescue
reached `0.4074074074074074`, and every fixed-time RTH premium rescue had a
`0.0` profitable-combo rate. The already-run ID/NR4 and ES/MES rescues failed
the random-placebo monkey median/profitability gates, and the already-run
high-gap overnight short rescue failed core at `0.691358024691358`.

No active rescued variant produced a candidate strategy for manual chart review
or paper incubation. No second rescue is permitted for these variants under the
current per-failed-variant rule. Consolidated audit:
`research_artifacts/all_failed_variant_rescue_audit_20260615.md`.

## Verification

- `python3 -m pytest tests/test_backtest_engine.py tests/test_campaign_stages.py tests/test_preflight.py`: PASS, 71 tests.
- `python3 -m pytest`: PASS, 348 tests.
- `python3 -m research.preflight --pytest-args "tests/test_backtest_engine.py tests/test_campaign_stages.py tests/test_preflight.py"`: PASS, 58 configs checked.
- `python3 -m pytest tests/test_config_layout.py tests/test_preflight.py`: PASS, 22 tests.
- `python3 -m research.preflight --skip-tests`: PASS, 66 configs checked.
- Active summary sweep over `backtest-campaigns/**/campaign_test_summary.json`: no active variant-level report has `passed=true`; all active runnable reports halted before WFA or are aggregate campaign summaries.
- `python3 -m research.preflight --config campaigns/es_mes_micro_flow_divergence_reversion/rescue_attempts/parameter_space_rescue_1/afternoon_mes_large20_sell_pressure_long/config.yaml --skip-tests`: PASS, 1 config checked.
- `python3 -m propstack.run_campaign_stages --config campaigns/es_mes_micro_flow_divergence_reversion/rescue_attempts/parameter_space_rescue_1/afternoon_mes_large20_sell_pressure_long/config.yaml --skip-validation`: completed, failed at `limited_monkey_test`.
- `python3 -m research.preflight --config campaigns/es_mes_micro_flow_divergence_reversion/rescue_attempts/parameter_space_rescue_1/morning_mes_buy_pressure_reversion_short/config.yaml --skip-tests`: PASS, 1 config checked.
- `python3 -m propstack.run_campaign_stages --config campaigns/es_mes_micro_flow_divergence_reversion/rescue_attempts/parameter_space_rescue_1/morning_mes_buy_pressure_reversion_short/config.yaml --skip-validation`: completed, failed at `limited_monkey_test`.
- `python3 -m research.preflight --skip-tests`: PASS, 68 configs checked.
- `python3 -m propstack.run_campaign_stages --config campaigns/es_mes_micro_flow_divergence_reversion/rescue_attempts/parameter_space_rescue_1/afternoon_mes_large20_buy_pressure_short/config.yaml --fast-runtime-defaults`: completed, failed at `limited_monkey_test`.
- `python3 -m research.preflight --skip-tests`: PASS, 69 configs checked.
- `python3 -m propstack.run_campaign_stages --config campaigns/es_mes_micro_flow_divergence_reversion/rescue_attempts/parameter_space_rescue_1/morning_mes_sell_pressure_reversion_long/config.yaml --fast-runtime-defaults`: completed, failed at `limited_monkey_test`.
- `python3 -m pytest tests/test_config_layout.py tests/test_preflight.py`: PASS, 22 tests.
- `python3 -m research.preflight --skip-tests`: PASS, 70 configs checked.
- Targeted rescue preflight loop over `campaigns/*/rescue_attempts/parameter_space_rescue_1/*/config.yaml`: PASS, 30 rescue configs checked.
- Staged rescue loop over the 23 missing `rescue1` reports using `python3 -m propstack.run_campaign_stages --config <config> --fast-runtime-defaults`: completed; all 23 failed.
- Active ES variant-level summary sweep over 73 `campaign_test_summary.json` files after adding `es_signed_orderflow_persistence`: no report has `passed=true`; active variants missing `rescue1` report: `0`.
- `python3 -m research.preflight --skip-tests`: PASS, 93 configs checked after adding the missing rescue configs.
- `python3 -m pytest tests/test_preflight.py tests/test_config_layout.py`: PASS, 23 tests, including archive-path exclusion for active config discovery.
- `python3 -m research.preflight --skip-tests`: PASS, 108 active configs checked after adding `es_signed_orderflow_persistence` and applying archive-path exclusion.
- `python3 -m research.preflight --skip-tests --config <five es_signed_orderflow_persistence original configs>`: PASS, 5 configs checked.
- `python3 -m research.preflight --skip-tests --config <five es_signed_orderflow_persistence rescue configs>`: PASS, 5 configs checked.
- `python3 -m propstack.run_campaign_stages --config <each es_signed_orderflow_persistence original/rescue config> --fast-runtime-defaults`: completed, all 10 runs failed at `limited_core_grid_test`.

## Final Decision

FAIL

No strategy is a candidate for manual chart review or paper incubation from this run. Continuing the search without violating the duplicate-edge rule requires avoiding the currently active rejected edge families, now including own-ES signed-orderflow persistence; archived tests no longer block a fresh campaign by themselves.
