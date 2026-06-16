# Futures Backtest Methodology Audit

Audit date: 2026-06-15

Overall status: FAIL

Reason: the engine/preflight path now passes focused sanity checks, but no ES strategy candidate in the active search passed the corrected staged methodology. Active ES campaigns, including the latest BLS macro release-day drift campaign, failed before WFA under the corrected objective gates. The completed per-failed-variant rescue attempts also failed before WFA.

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

### `es_opening_drive_inventory_absorption`

Source thesis: first-30/60-minute opening drives can contain same-day
information when paired with volume and orderflow state, but may reverse when
inventory pressure is absorbed. The campaign combined intraday momentum,
intraday return/flow timing, and orderflow-impact literature.

Data: corrected local ES Sierra aggregate orderflow cache from `2011-01-03`
through `2026-06-09`.

| Variant | Original terminal | Original pct | Rescue terminal | Rescue pct | Decision |
| --- | --- | ---: | --- | ---: | --- |
| `open30_flow_continuation_1030` | `limited_core_grid_test` | `0.38271604938271603` | `limited_core_grid_test` | `0.35802469135802467` | FAIL |
| `open60_flow_continuation_1130` | `limited_monkey_test` | `0.16333333333333333` | `limited_monkey_test` | `0.20666666666666667` | FAIL |
| `open30_absorbed_pressure_fade_1015` | `limited_core_grid_test` | `0.0` | `limited_core_grid_test` | `0.0` | FAIL |
| `open60_exhaustion_fade_1300` | `limited_core_grid_test` | `0.5555555555555556` | `limited_core_grid_test` | `0.4074074074074074` | FAIL |
| `open30_price_flow_divergence_fade_1400` | `limited_core_grid_test` | `0.0` | `limited_core_grid_test` | `0.0` | FAIL |

Decision: FAIL. No run reached WFA. The two
`open60_flow_continuation_1130` runs passed core but failed monkey with weak
profitable-run rates and failed one-tick-worse stress. Report:
`backtest-campaigns/es_opening_drive_inventory_absorption/campaign_test_summary.json`.
Audit:
`research_artifacts/es_opening_drive_inventory_absorption_rescue_attempt_1_20260615.md`.

### `es_turn_of_month_seasonality`

Source thesis: equity-index futures may retain a positive turn-of-the-month
calendar premium around month-end and the first calendar days of the next month.
The campaign tested this as a calendar-seasonality edge, distinct from the
unconditional fixed RTH long-bias campaign.

Data: corrected local ES Sierra RTH OHLCV/orderflow cache from `2011-01-03`
through `2026-06-09`, aggregated to 5-minute strategy bars.

| Variant | Original profitable combo rate | Original top net / trades | Rescue profitable combo rate | Rescue top net / trades | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `classic_turn_window_1000_long` | `0.037037037037037035` | `577.5` / `62` | `0.0` | `-96.25` / `73` | FAIL |
| `early_month_first_days_1000_long` | `0.0` | `-287.5` / `25` | `0.07407407407407407` | `178.75` / `13` | FAIL |
| `month_end_last_days_1000_long` | `0.3333333333333333` | `1991.25` / `48` | `0.0` | `-206.25` / `60` | FAIL |
| `opening_turn_window_0935_long` | `0.04938271604938271` | `355.0` / `74` | `0.07407407407407407` | `1685.0` / `73` | FAIL |
| `late_turn_window_1300_long` | `0.0` | `-810.0` / `97` | `0.0` | `-352.5` / `73` | FAIL |

Decision: FAIL. All five original variants and all five one-time
parameter-space-only rescues failed the `0.70` core profitable-combo gate before
monkey, WFA, Monte Carlo, or frozen validation. Report:
`backtest-campaigns/es_turn_of_month_seasonality/campaign_test_summary.json`.
Audit:
`research_artifacts/es_turn_of_month_seasonality_rescue_attempt_1_20260615.md`.

### `es_daily_time_series_momentum`

Source thesis: futures can exhibit time-series momentum, where an asset's own
prior returns predict same-direction continuation. The campaign tested this in
ES using only prior completed RTH closes and intraday same-day execution.

Data: corrected local ES Sierra RTH OHLCV/orderflow cache from `2011-01-03`
through `2026-06-09`, aggregated to 5-minute strategy bars.

| Variant | Original profitable combo rate | Original top net / trades | Rescue profitable combo rate | Rescue top net / trades | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `long_only_trend_1000` | `0.0` | `-572.5` / `142` | `0.2839506172839506` | `2822.5` / `123` | FAIL |
| `short_term_alignment_1000_two_sided` | `0.0` | `-6951.25` / `239` | `0.0` | `-3692.5` / `121` | FAIL |
| `sixty_day_trend_1000_two_sided` | `0.0` | `-6626.25` / `269` | `0.19753086419753085` | `2822.5` / `123` | FAIL |
| `twenty_day_trend_1000_two_sided` | `0.0` | `-7438.75` / `299` | `0.0` | `-7776.25` / `354` | FAIL |
| `vol_norm_trend_1000_two_sided` | `0.012345679012345678` | `452.5` / `92` | `0.14814814814814814` | `1392.5` / `89` | FAIL |

Decision: FAIL. All five original variants and all five one-time
parameter-space-only rescues failed the `0.70` core profitable-combo gate before
monkey, WFA, Monte Carlo, or frozen validation. The strongest rescue was still a
narrow surface at `0.2839506172839506`. Report:
`backtest-campaigns/es_daily_time_series_momentum/campaign_test_summary.json`.
Audit:
`research_artifacts/es_daily_time_series_momentum_rescue_attempt_1_20260615.md`.

### `es_late_day_intraday_momentum`

Source thesis: Gao, Han, Li, and Zhou's market intraday momentum anomaly states
that the first half-hour market return measured from the prior close predicts
the last half-hour return. The campaign tested whether that survives as a
same-day ES futures strategy with realistic costs and flattening.

Data: corrected local ES Sierra RTH OHLCV/orderflow cache from `2011-01-03`
through `2026-06-09`, aggregated to 5-minute strategy bars with
`feature_set: pdh_pdl_sweep` for prior-RTH close and volume-ratio features.

Feature-audit note: an initial zero-trade run used `feature_set: none`, which
did not build `prev_rth_close` or `volume_ratio`. Those invalid outputs were
removed and the original `run1` was rerun with the corrected feature set before
any rescue was consumed.

| Variant | Original profitable combo rate | Original top net / trades | Rescue profitable combo rate | Rescue top net / trades | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `first30_to_last30_two_sided` | `0.0` | `-6765.0` / `253` | `0.0` | `-2941.25` / `72` | FAIL |
| `first30_to_last30_long_only` | `0.0` | `-2697.5` / `137` | `0.0` | `-742.5` / `76` | FAIL |
| `first30_volume_range_conditioned` | `0.0` | `-3270.0` / `164` | `0.0` | `-912.5` / `35` | FAIL |
| `first60_to_last30_two_sided` | `0.0` | `-5220.625` / `186` | `0.0` | `-2316.25` / `57` | FAIL |
| `first30_penultimate_alignment` | `0.0` | `-1902.5` / `68` | `0.0` | `-240.0` / `8` | FAIL |

Decision: FAIL. All five original variants and all five one-time
parameter-space-only rescues had `0.0` profitable core-grid combinations and
failed before monkey, WFA, Monte Carlo, or frozen validation. Report:
`backtest-campaigns/es_late_day_intraday_momentum/campaign_test_summary.json`.
Audit:
`research_artifacts/es_late_day_intraday_momentum_rescue_attempt_1_20260615.md`.

### `es_volume_shock_liquidity_reversal`

Source thesis: high-volume return shocks can have different serial-correlation
properties depending on whether they reflect liquidity/risk-sharing pressure or
information. The campaign tested completed high-volume 5-minute ES shock bars
as liquidity-reversal candidates.

Data: corrected local ES Sierra RTH OHLCV/orderflow cache from `2011-01-03`
through `2026-06-09`, aggregated to 5-minute strategy bars with
`feature_set: pdh_pdl_sweep` for rolling volume-ratio features.

| Variant | Original profitable combo rate | Original top net / trades | Rescue profitable combo rate | Rescue top net / trades | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `all_day_symmetric_shock_reversion` | `0.0` | `0.0` / `0` | `0.024691358024691357` | `397.5` / `33` | FAIL |
| `morning_down_shock_reversal_long` | `0.06172839506172839` | `215.0` / `142` | `0.1728395061728395` | `1257.5` / `11` | FAIL |
| `morning_up_shock_reversal_short` | `0.04938271604938271` | `532.5` / `6` | `0.08641975308641975` | `2167.5` / `29` | FAIL |
| `midday_symmetric_shock_reversion` | `0.024691358024691357` | `617.5` / `34` | `0.20987654320987653` | `1866.25` / `13` | FAIL |
| `afternoon_symmetric_shock_reversion` | `0.037037037037037035` | `508.75` / `67` | `0.06172839506172839` | `1770.0` / `36` | FAIL |

Decision: FAIL. All five original variants and all five one-time
parameter-space-only rescues failed the `0.70` core profitable-combo gate before
monkey, WFA, Monte Carlo, or frozen validation. The best rescue reached only
`0.20987654320987653` profitable combinations and its top row had only `13`
trades. Report:
`backtest-campaigns/es_volume_shock_liquidity_reversal/campaign_test_summary.json`.
Audit:
`research_artifacts/es_volume_shock_liquidity_reversal_rescue_attempt_1_20260615.md`.

### `es_prior_day_stop_run_reclaim`

Source thesis: prior-session highs and lows are salient support/resistance
levels where clustered stop orders and liquidity provision can create failed
breakouts. The campaign tested whether completed 5-minute ES sweeps through the
prior RTH high/low that closed back inside the level could be faded same day.

Data: corrected local ES Sierra RTH OHLCV/orderflow cache from `2011-01-03`
through `2026-06-09`, aggregated to 5-minute strategy bars with
`feature_set: pdh_pdl_sweep` for prior-RTH high/low and volume-ratio features.

| Variant | Original profitable combo rate | Original terminal stage | Rescue profitable/monkey rate | Rescue terminal stage | Decision |
| --- | ---: | --- | ---: | --- | --- |
| `full_session_two_sided_reclaim` | `0.012345679012345678` | `limited_core_grid_test` | `0.2716049382716049` | `limited_core_grid_test` | FAIL |
| `morning_prior_low_reclaim_long` | `0.1728395061728395` | `limited_core_grid_test` | `0.654320987654321` | `limited_core_grid_test` | FAIL |
| `morning_prior_high_reject_short` | `0.14814814814814814` | `limited_core_grid_test` | `0.32666666666666666` | `limited_monkey_test` | FAIL |
| `midday_two_sided_reclaim` | `0.2716049382716049` | `limited_core_grid_test` | `0.2222222222222222` | `limited_core_grid_test` | FAIL |
| `afternoon_two_sided_reclaim` | `0.12345679012345678` | `limited_core_grid_test` | `0.345679012345679` | `limited_core_grid_test` | FAIL |

Decision: FAIL. All five original variants and all five one-time
parameter-space-only rescues failed before WFA. The strongest rescue,
`morning_prior_high_reject_short/rescue1`, passed the core profitable-combo
gate with `0.8641975308641975` profitable combinations, but failed
`limited_monkey_test` with `percentage_profitable=0.32666666666666666` and
`median_net_profit=-770.0`. Report:
`backtest-campaigns/es_prior_day_stop_run_reclaim/campaign_test_summary.json`.
Audit:
`research_artifacts/es_prior_day_stop_run_reclaim_rescue_attempt_1_20260615.md`.

### `es_vwap_pullback_continuation`

Source thesis: VWAP is a common institutional execution benchmark and intraday
value reference; a completed pullback or failed break around the developing
session VWAP may continue in the established intraday direction when the market
reclaims the trend side of VWAP.

Data: corrected local ES Sierra RTH OHLCV/orderflow cache from `2011-01-03`
through `2026-06-09`, aggregated to 5-minute strategy bars with developing VWAP
computed only from bars available at decision time.

| Variant | Original profitable combo rate | Original terminal stage | Rescue profitable/monkey rate | Rescue terminal stage | Decision |
| --- | ---: | --- | ---: | --- | --- |
| `morning_trend_reclaim_two_sided` | `0.012345679012345678` | `limited_core_grid_test` | `0.1111111111111111` | `limited_core_grid_test` | FAIL |
| `morning_opening_drive_pullback_long` | `0.1728395061728395` | `limited_core_grid_test` | `0.14814814814814814` | `limited_core_grid_test` | FAIL |
| `morning_opening_drive_pullback_short` | `0.037037037037037035` | `limited_core_grid_test` | `0.2345679012345679` | `limited_core_grid_test` | FAIL |
| `midday_trend_reclaim_two_sided` | `0.2222222222222222` | `limited_core_grid_test` | `0.18` | `limited_monkey_test` | FAIL |
| `failed_vwap_break_two_sided` | `0.12345679012345678` | `limited_core_grid_test` | `0.24691358024691357` | `limited_core_grid_test` | FAIL |

Decision: FAIL. All five original variants and all five one-time
parameter-space-only rescues failed before WFA. The strongest rescue,
`midday_trend_reclaim_two_sided/rescue1`, passed the core profitable-combo gate
with `0.8148148148148148` profitable combinations, but failed
`limited_monkey_test` with `percentage_profitable=0.18` and
`median_net_profit=-3210.0`. Report:
`backtest-campaigns/es_vwap_pullback_continuation/campaign_test_summary.json`.
Audit:
`research_artifacts/es_vwap_pullback_continuation_rescue_attempt_1_20260615.md`.

### `es_cftc_tff_hedging_pressure`

Source thesis: weekly CFTC Traders in Financial Futures positioning may proxy
slow-moving equity-index hedging pressure. ES intraday returns may compensate
traders who take the other side of that risk-transfer pressure after the report
feature is available.

Data: corrected local ES Sierra RTH OHLCV/orderflow cache from `2013-04-15`
through `2026-06-09`, plus local shifted CFTC TFF
`SPX_open_interest_chg13` features from
`data/external/cftc_tff_hedging_pressure_features.csv`.

Invalidated run note: initial `run1` artifacts are not economic evidence. The
limited-core first-window sample started before non-null shifted CFTC feature
coverage and produced zero trades. The valid originals are `run2`.

| Variant | Valid original profitable combo rate | Rescue profitable combo rate | Rescue top net / trades | Decision |
| --- | ---: | ---: | ---: | --- |
| `broad_negative_pressure_short_1100` | `0.0` | `0.0` | `-1208.75` / `103` | FAIL |
| `broad_positive_pressure_long_1100` | `0.14814814814814814` | `0.0` | `-2465.0` / `58` | FAIL |
| `extreme_negative_pressure_short_1330` | `0.1111111111111111` | `0.18518518518518517` | `262.5` / `5` | FAIL |
| `extreme_positive_pressure_long_1330` | `0.0` | `0.3333333333333333` | `775.0` / `5` | FAIL |
| `high_positive_pressure_long_0935` | `0.0` | `0.1111111111111111` | `915.625` / `5` | FAIL |

Decision: FAIL. All five corrected originals and all five one-time
parameter-space-only rescues failed the `0.70` core profitable-combo gate before
monkey, WFA, Monte Carlo, or frozen validation. The best rescue reached only
`0.3333333333333333` profitable combinations and its top row had only `5`
trades. Report:
`backtest-campaigns/es_cftc_tff_hedging_pressure/campaign_test_summary.json`.
Audit:
`research_artifacts/es_cftc_tff_hedging_pressure_rescue_attempt_1_20260615.md`.

## Duplicate-Edge Scope

- No local ES `campaign_test_summary.json` currently has `passed=true`.
- Archived tests are ignored when checking whether a proposed campaign is a duplicate edge. They remain historical evidence only and must not block a fresh campaign by themselves.
- The duplicate-edge gate now compares only against active `campaigns/`, active `backtest-campaigns/`, and current non-archived `research_ledger.csv` rows.
- Active rejected edge families from this run remain blocked from relaunch under a new active name: ES/MES micro-flow divergence, prior-session IBS, Connors RSI2, range-compression breakout, RTH intraday risk premium, overnight-intraday reversal, own-ES signed-orderflow persistence, opening-drive inventory/absorption, turn-of-month seasonality, daily time-series momentum, late-day market intraday momentum, volume-shock liquidity reversal, prior-day stop-run reclaim, VWAP pullback continuation, and CFTC/TFF hedging pressure.
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
variants, the current conclusion remains fail-closed for the active set.

## Rescue Decision

All 75 active failed ES variants now have exactly one `rescue1` report. The 23
previously unrescued variants were given parameter-only rescue runs after the
user clarified that each failed variant can be rescued once. Existing `rescue1`
reports were not rerun, and no second rescue was created for any variant. The
later `es_signed_orderflow_persistence` campaign added five more failed variants
and five completed `rescue1` runs. The later
`es_opening_drive_inventory_absorption` campaign added five more failed
variants and five completed `rescue1` runs. The later
`es_turn_of_month_seasonality` campaign added five more failed variants and five
completed `rescue1` runs. The later `es_daily_time_series_momentum` campaign
added five more failed variants and five completed `rescue1` runs. The later
`es_late_day_intraday_momentum` campaign added five more failed variants and
five completed `rescue1` runs. The later
`es_volume_shock_liquidity_reversal` campaign added five more failed variants
and five completed `rescue1` runs. The later
`es_prior_day_stop_run_reclaim` campaign added five more failed variants and
five completed `rescue1` runs. The later
`es_vwap_pullback_continuation` campaign added five more failed variants and
five completed `rescue1` runs. The later
`es_cftc_tff_hedging_pressure` campaign added five more failed variants and
five completed `rescue1` runs.

Every rescue failed before WFA or at `limited_monkey_test`. The strongest
remaining surfaces still failed objective gates: the best new IBS rescue reached
only `0.5061728395061729` profitable core combinations, the best new Connors
RSI2 rescue reached `0.345679012345679`, the best new range-compression rescue
reached `0.4074074074074074`, and every fixed-time RTH premium rescue had a
`0.0` profitable-combo rate. The already-run ID/NR4 and ES/MES rescues failed
the random-placebo monkey median/profitability gates, and the already-run
high-gap overnight short rescue failed core at `0.691358024691358`.
The opening-drive inventory/absorption campaign failed before WFA; its best
rescue core rate was `0.4074074074074074`, and the only rescue to reach monkey
had `percentage_profitable=0.20666666666666667` with one-tick-worse stress
failing.
The turn-of-month seasonality campaign failed before monkey; its best rescue
core rate was only `0.07407407407407407`.
The daily time-series momentum campaign failed before monkey; its best rescue
core rate was only `0.2839506172839506`.
The late-day market intraday momentum campaign failed before monkey; every
original and rescue core grid had `0.0` profitable combinations.
The volume-shock liquidity reversal campaign failed before monkey; its best
rescue core rate was only `0.20987654320987653`, with only `13` top-row trades.
The prior-day stop-run reclaim campaign failed before WFA; its strongest rescue
passed the core profitable-combo gate but failed monkey with
`percentage_profitable=0.32666666666666666` and `median_net_profit=-770.0`.
The VWAP pullback-continuation campaign failed before WFA; its strongest rescue
passed the core profitable-combo gate but failed monkey with
`percentage_profitable=0.18` and `median_net_profit=-3210.0`.
The CFTC/TFF hedging-pressure campaign failed before WFA; its best rescue core
rate was only `0.3333333333333333`, with only `5` top-row trades.

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
- `python3 -m research.preflight --skip-tests --config <five es_opening_drive_inventory_absorption original configs>`: PASS, 5 configs checked.
- `python3 -m research.preflight --skip-tests --config <five es_opening_drive_inventory_absorption rescue configs>`: PASS, 5 configs checked.
- `python3 -m propstack.run_campaign_stages --config <each es_opening_drive_inventory_absorption original/rescue config> --fast-runtime-defaults`: completed, all 10 valid runs failed before WFA; one transient process-pool error was rerun with the same frozen rescue config and completed normally.
- `python3 -m research.preflight --skip-tests`: PASS, 123 active configs checked after adding `es_opening_drive_inventory_absorption`.
- Active ES variant-level summary sweep over 83 `campaign_test_summary.json` files after adding `es_opening_drive_inventory_absorption`: no report has `passed=true`; active variants missing `rescue1` report: `0`.
- `python3 -m research.preflight --skip-tests --config <five es_turn_of_month_seasonality original configs>`: PASS, 5 configs checked.
- `python3 -m research.preflight --skip-tests --config <five es_turn_of_month_seasonality rescue configs>`: PASS, 5 configs checked.
- `python3 -m pytest tests/test_preflight.py tests/test_config_layout.py tests/test_backtest_engine.py tests/test_campaign_stages.py`: PASS, 87 tests.
- `python3 -m propstack.run_campaign_stages --config <each es_turn_of_month_seasonality original/rescue config> --fast-runtime-defaults`: completed, all 10 runs failed at `limited_core_grid_test`.
- `python3 -m research.preflight --skip-tests`: PASS, 138 active configs checked after adding `es_turn_of_month_seasonality`.
- Active ES variant-level summary sweep over 93 `variant_test_summary.json` files after adding `es_turn_of_month_seasonality`: no report has `passed=true`; active variants missing `rescue1` report: `0`.
- `python3 -m research.preflight --skip-tests --config <five es_daily_time_series_momentum original configs>`: PASS, 5 configs checked.
- `python3 -m research.preflight --skip-tests --config <five es_daily_time_series_momentum rescue configs>`: PASS, 5 configs checked.
- `python3 -m propstack.run_campaign_stages --config <each es_daily_time_series_momentum original/rescue config> --fast-runtime-defaults`: completed, all 10 runs failed at `limited_core_grid_test`.
- `python3 -m research.preflight --skip-tests`: PASS, 153 active configs checked after adding `es_daily_time_series_momentum`.
- Active ES variant-level summary sweep over 103 `variant_test_summary.json` files after adding `es_daily_time_series_momentum`: no report has `passed=true`; active variants missing `rescue1` report: `0`.
- `python3 -m research.preflight --skip-tests --config <five es_late_day_intraday_momentum original configs>`: PASS, 5 configs checked.
- `python3 -m pytest tests/test_strategy_modules.py -k 'late_day_intraday_momentum'`: PASS, 5 tests.
- `python3 -m propstack.run_campaign_stages --config <each es_late_day_intraday_momentum original/rescue config> --fast-runtime-defaults`: completed, all 10 corrected runs failed at `limited_core_grid_test`.
- `python3 -m research.preflight --skip-tests --config <five es_late_day_intraday_momentum rescue configs>`: PASS, 5 configs checked.
- `python3 -m research.preflight --skip-tests`: PASS, 168 active configs checked after adding `es_late_day_intraday_momentum`.
- Active ES variant-level summary sweep over 113 `campaign_test_summary.json` files after adding `es_late_day_intraday_momentum`: no report has `passed=true`; active variants missing `rescue1` report: `0`.
- `python3 -m research.preflight --skip-tests --config <five es_volume_shock_liquidity_reversal original configs>`: PASS, 5 configs checked.
- `python3 -m pytest tests/test_strategy_modules.py -k 'volume_conditioned_liquidity_reversal'`: PASS, 2 tests.
- `python3 -m propstack.run_campaign_stages --config <each es_volume_shock_liquidity_reversal original/rescue config> --fast-runtime-defaults`: completed, all 10 runs failed at `limited_core_grid_test`.
- `python3 -m research.preflight --skip-tests --config <five es_volume_shock_liquidity_reversal rescue configs>`: PASS, 5 configs checked.
- `python3 -m research.preflight --skip-tests`: PASS, 183 active configs checked after adding `es_volume_shock_liquidity_reversal`.
- Active ES variant-level summary sweep over 123 `campaign_test_summary.json` files after adding `es_volume_shock_liquidity_reversal`: no report has `passed=true`; active variants missing `rescue1` report: `0`.
- `python3 -m pytest tests/test_preflight.py tests/test_config_layout.py tests/test_backtest_engine.py tests/test_campaign_stages.py`: PASS, 87 tests after adding `es_volume_shock_liquidity_reversal`.
- `python3 -m research.preflight --skip-tests --config <five es_prior_day_stop_run_reclaim original configs>`: PASS, 5 configs checked.
- `python3 -m pytest tests/test_strategy_modules.py -k 'pdh_pdl_entry'`: PASS, 6 tests.
- `python3 -m propstack.run_campaign_stages --config <each es_prior_day_stop_run_reclaim original/rescue config> --fast-runtime-defaults`: completed, all 10 runs failed before WFA; one rescue reached and failed `limited_monkey_test`, the others failed `limited_core_grid_test`.
- `python3 -m research.preflight --skip-tests --config <five es_prior_day_stop_run_reclaim rescue configs>`: PASS, 5 configs checked.
- `python3 -m research.preflight --skip-tests`: PASS, 198 active configs checked after adding `es_prior_day_stop_run_reclaim`.
- Active ES variant-level summary sweep over 133 `campaign_test_summary.json` files after adding `es_prior_day_stop_run_reclaim`: no report has `passed=true`; active variants missing `rescue1` report: `0`.
- `python3 -m pytest tests/test_preflight.py tests/test_config_layout.py tests/test_backtest_engine.py tests/test_campaign_stages.py`: PASS, 87 tests after adding `es_prior_day_stop_run_reclaim`.
- `python3 -m research.preflight --skip-tests --config <five es_vwap_pullback_continuation original configs>`: PASS, 5 configs checked.
- `python3 -m pytest tests/test_strategy_modules.py -k 'vwap_pullback_continuation'`: PASS, 6 tests.
- `python3 -m propstack.run_campaign_stages --config <each es_vwap_pullback_continuation original/rescue config> --fast-runtime-defaults`: completed, all 10 runs failed before WFA; one rescue reached and failed `limited_monkey_test`, the others failed `limited_core_grid_test`.
- `python3 -m research.preflight --skip-tests --config <five es_vwap_pullback_continuation rescue configs>`: PASS, 5 configs checked.
- `python3 -m research.preflight --skip-tests`: PASS, 213 active configs checked after adding `es_vwap_pullback_continuation`.
- Active ES variant-level summary sweep over 143 raw active `campaign_test_summary.json` files after adding `es_vwap_pullback_continuation`: no report has `passed=true`; 70 latest original reports and 70 `rescue1` reports exist for the 70 active source variants; active variants missing `rescue1` report: `0`.
- `python3 -m pytest tests/test_preflight.py tests/test_config_layout.py tests/test_backtest_engine.py tests/test_campaign_stages.py`: PASS, 87 tests after adding `es_vwap_pullback_continuation`.
- `python3 -m research.preflight --skip-tests --config <five es_cftc_tff_hedging_pressure corrected original configs>`: PASS, 5 configs checked.
- `python3 -m pytest tests/test_strategy_modules.py -k 'cftc_tff'`: PASS, 3 tests.
- `python3 -m propstack.run_campaign_stages --config <each es_cftc_tff_hedging_pressure corrected original/rescue config> --fast-runtime-defaults`: completed, all 10 valid runs failed at `limited_core_grid_test`. Initial `run1` artifacts were invalidated because they predated non-null shifted CFTC feature coverage.
- `python3 -m research.preflight --skip-tests --config <five es_cftc_tff_hedging_pressure rescue configs>`: PASS, 5 configs checked.
- `python3 -m research.preflight --skip-tests`: PASS, 233 active configs checked after adding `es_cftc_tff_hedging_pressure`.
- Active ES variant-level summary sweep over 158 raw active `campaign_test_summary.json` files after adding `es_cftc_tff_hedging_pressure`: no report has `passed=true`; 75 latest original reports and 75 `rescue1` reports exist for the 75 active source variants; active variants missing `rescue1` report: `0`.

## Final Decision

FAIL

No strategy is a candidate for manual chart review or paper incubation from this run. Continuing the search without violating the duplicate-edge rule requires avoiding the currently active rejected edge families, now including own-ES signed-orderflow persistence, opening-drive inventory/absorption, turn-of-month seasonality, daily time-series momentum, late-day market intraday momentum, volume-shock liquidity reversal, prior-day stop-run reclaim, VWAP pullback continuation, and CFTC/TFF hedging pressure; archived tests no longer block a fresh campaign by themselves.

## ES Market Plumbing Liquidity Capacity - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_market_plumbing_liquidity_capacity/campaign.yaml` and exactly five variants using the existing `market_plumbing_priority` entry module with `percent_from_entry` stops and `fixed_r` targets.
- Created conservative lagged feature file `data/external/market_plumbing_priority_features_lag1_no_lookahead.csv`; source-row values are shifted by one listed trade date before use.
- Invalidated initial `run1` artifacts because `data.feature_set` used an unsupported descriptive label; corrected valid originals are `run2` with unchanged mechanics, parameters, timeframe, and data window.
- Original `run2` results: four variants failed `limited_core_grid_test`; `dealer_lending_pressure_long_1330` passed core at 0.7777777777777778 profitable combos but failed `limited_monkey_test` with percentage_profitable=0.25333333333333335 and median_net_profit=-1962.5.
- Rescue `rescue1` results: four variants failed `limited_core_grid_test`; `dual_pressure_priority_long_1130` passed core at 0.8888888888888888 profitable combos but failed `limited_monkey_test` with percentage_profitable=0.3466666666666667 and median_net_profit=-1665.0.
- No run reached WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_strategy_modules.py -k market_plumbing_priority` PASS; `python3 -m research.preflight --skip-tests` PASS with 248 active configs after rescues.

## ES Bankruptcy Distress Regime Reversion - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_bankruptcy_distress_regime_reversion/campaign.yaml` and exactly five variants using `bankruptcy_distress_reversion`, `percent_from_entry`, and `fixed_r`.
- Used only derived U.S. Courts F-2 YoY/share/z-score features with explicit `effective_date`; raw parsed count columns were not signal inputs.
- Invalidated `run1` zero-trade artifacts because the limited-core first-window sample predated shared elevated-distress feature coverage; corrected `run2` changed only `start_date` to `2016-08-15`.
- Corrected originals: all five failed `limited_core_grid_test` with 0.0 profitable-combo rate.
- Rescues: all five one-time parameter-space-only rescues failed `limited_core_grid_test`; no run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.
- Verification: `python3 -m pytest tests/test_strategy_modules.py -k bankruptcy_distress_reversion` PASS; `python3 -m research.preflight --skip-tests` PASS with 268 active configs before rescue execution.


## ES Prior-Session Level Breakout Continuation - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_prior_session_level_breakout_continuation/campaign.yaml` and exactly five variants using `pdh_pdl_breakout_continuation`, `percent_from_entry`, and `fixed_r`.
- Duplicate-edge check used active-only scope. This is distinct from active `es_prior_day_stop_run_reclaim`: it enters with confirmed breaks/holds outside prior RTH high/low rather than fading failed sweeps that close back inside.
- Original runs: all five failed `limited_core_grid_test`; best original was `morning_prior_high_breakout_long` at `0.691358024691358` profitable combinations, below the `0.70` core gate.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed. `gap_hold_two_sided_continuation` failed core at `0.654320987654321`; the other four passed core but failed `limited_monkey_test` with monkey profitable rates from `0.2` to `0.3466666666666667` and negative median net profit.
- No run reached WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m research.preflight --skip-tests` PASS with `288` active configs after aggregate artifacts were written; active sweep found `90` source variants, `90` rescue configs, `198` raw variant reports, `0` passes, and no missing original/rescue reports.


## ES VPIN Toxicity Continuation - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_vpin_toxicity_continuation/campaign.yaml` and exactly five variants using `vpin_toxicity_continuation`, `percent_from_entry`, and `fixed_r`.
- Duplicate-edge check used active-only scope. This is distinct from active raw signed-flow persistence and opening-drive inventory because it tests shifted prior-session VPIN/order-flow-toxicity proxy ranks at 13:30 ET.
- Data caveat: this is an OHLCV volume-bucket toxicity proxy, not tick-level VPIN with true buyer/seller classification.
- Original runs: four failed `limited_core_grid_test`; `slow_bucket_toxicity_long_1330` passed core at `0.8271604938271605` but failed `limited_monkey_test`.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed. `slow_bucket_toxicity_long_1330` rescue passed core at `1.0` profitable combinations but failed `limited_monkey_test`; the other four failed core.
- No run reached WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_strategy_modules.py tests/test_features.py -k vpin` PASS; `python3 -m research.preflight --skip-tests` PASS with `303` active configs; active sweep found `95` source variants, `95` rescue configs, `208` raw variant reports, `0` passes, and no missing original/rescue reports.


## ES Overnight Return Late-Day Momentum - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_overnight_return_late_day_momentum/campaign.yaml` and exactly five variants using `overnight_return_late_day_momentum`, `percent_from_entry`, and `fixed_r`.
- Duplicate-edge check used active-only scope. This is distinct from active early overnight-intraday reversal and first/last-window late-day intraday momentum because it uses prior-close-to-RTH-open overnight return as the late-day predictor.
- Original runs: all five failed `limited_core_grid_test` with `0.0` profitable-combo rate.
- Rescues: all five one-time parameter-space/fixed-parameter rescues also failed `limited_core_grid_test` with `0.0` profitable-combo rate.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_strategy_modules.py -k overnight_return_late_day_momentum` PASS; `python3 -m research.preflight --skip-tests` PASS with `318` active configs; active sweep found `100` source variants, `100` rescue configs, `218` raw variant reports, `0` passes, and no missing original/rescue reports.


## ES Prior-Level Delta Dislocation - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_prior_level_delta_dislocation/campaign.yaml` and exactly five variants using `positive_delta_dislocation`, `percent_from_entry`, and `fixed_r`.
- Duplicate-edge check used active-only scope and ignored archived tests. This is distinct from active prior-level reclaim and breakout campaigns because it requires completed rolling 60-minute price/orderflow disagreement at prior RTH extremes.
- Originals: all five failed `limited_core_grid_test` with zero trades because the fixed fresh-level requirement was too restrictive at 60-minute signal boundaries.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed after disabling only the fixed fresh-level requirement and adjusting declared thresholds. All five failed `limited_core_grid_test`; best rescue was `pdl_sell_absorption_long/rescue1` with `0.5555555555555556` profitable combinations, `437.5` top net, and `15` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_strategy_modules.py tests/test_features.py -k 'positive_delta_dislocation or trade_orderflow or previous_rth_freshness'` PASS; `python3 -m research.preflight --skip-tests` PASS with `333` configs after aggregate artifacts; active sweep found `105` source variants, `105` rescue configs, `228` raw variant reports, `0` passes, and no missing original/rescue reports.


## ES Orderflow Absorption Exhaustion Reversal - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_orderflow_absorption_exhaustion_reversal/campaign.yaml` and exactly five variants using `orderflow_regime`, `percent_from_entry`, and `fixed_r`.
- Duplicate-edge check used active-only scope and ignored archived tests. This is distinct from active signed-flow persistence because it fades extreme same-clock orderflow effort when price displacement is weak instead of following same-sign flow and return.
- Originals: one variant, `late_morning_15m_absorption_fade_1130`, passed core at `0.9382716049382716` profitable combinations but failed `limited_monkey_test` with monkey profitable rate `0.25` and median net `-190.0`; the other four failed core.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed and failed `limited_core_grid_test`.
- No run reached WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_strategy_modules.py tests/test_features.py -k 'orderflow_regime or trade_orderflow_same_clock_ranks or trade_orderflow_signed_toxicity_same_clock_rank'` PASS; `python3 -m research.preflight --skip-tests` PASS with `348` active configs; active sweep found `110` source variants, `110` rescue configs, `238` raw variant-level reports, `0` passes, and no missing original or `rescue1` reports.


## ES Day-of-Week Seasonality - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_day_of_week_seasonality/campaign.yaml` and exactly five variants using `calendar_session_bias`, `percent_from_entry`, and `fixed_r`.
- Duplicate-edge check used active-only scope and ignored archived tests. This is distinct from active `es_rth_intraday_risk_premium`, which tested unconditional all-weekday long RTH exposure, and distinct from active `es_turn_of_month_seasonality`, which tested monthly calendar windows.
- Originals: all five failed `limited_core_grid_test` with `0.0` profitable-combo rate. Best original was `monday_open_weekend_short_0935/run1` with top net `-800.0`, PF `0.9208508533267376`, and `65` top-combo trades.
- Rescues: all five one-time stop/target parameter-space rescues completed and failed `limited_core_grid_test` with `0.0` profitable-combo rate. Best rescue was `friday_open_preweekend_long_0935/rescue1` with top net `-1314.375`, PF `0.5172176308539945`, and `46` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_strategy_modules.py -k calendar_session_bias` PASS; `python3 -m research.preflight --skip-tests` PASS with `363` configs checked; active sweep found `115` source variants, `115` rescue configs, `248` raw variant-level reports, `0` passes, and no missing original or `rescue1` reports.


## ES Overnight Inventory Sweep Reversion - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_overnight_inventory_sweep_reversion/campaign.yaml` and exactly five variants using `overnight_inventory_reversion`, `percent_from_entry`, and `fixed_r`.
- Duplicate-edge check used active-only scope and ignored archived tests. This is distinct from active overnight gap/return reversal, overnight-return late-day continuation, and prior RTH level stop-run reclaim because it trades failed sweeps of completed ETH overnight high/low boundaries.
- Data audit: built `data/cache/databento/es_databento_ohlcv_1m_20100606_20260531_eth_rth_explicit_roll.parquet` from local monthly Databento OHLCV files using the explicit ES roll calendar, not same-day volume selection. Roll-boundary sessions are skipped in configs.
- Originals: `midpoint_low_sweep_reclaim_long/run1` passed core at `0.8271604938271605` profitable combinations but failed `limited_monkey_test` with monkey profitable rate `0.26` and median net `-601.25`; the other four originals failed `limited_core_grid_test`.
- Rescues: all five one-time parameter-space rescues completed and failed `limited_core_grid_test`.
- No run reached WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `pytest tests/test_strategy_modules.py -k overnight_inventory` PASS; `python3 -m research.preflight --skip-tests` PASS with `378` configs checked; active sweep found `120` source variants, `120` rescue configs, `258` raw variant-level reports, `0` passes, and no active variants missing a latest original or `rescue1` report.


## Active-Only Duplicate Recheck - 2026-06-16

Decision: FAIL.

- Archived tests remain ignored for duplicate-edge checks.
- Rechecked remaining unused local modules after `es_overnight_inventory_sweep_reversion`.
- Did not launch `intraday_capitulation_mr`: it is a stricter high-volume shock mean-reversion expression with RSI/VWAP filters and overlaps active volume-shock, Connors RSI/VWAP, and VWAP-context evidence.
- Did not launch pure opening-range breakout/fade: active `es_range_compression_breakout` already used opening-range breakout variants under the Crabel/NR7 compression thesis, so removing compression after active failures would relax mechanics post-result.
- Remaining local modules map to active intraday-momentum, signed-flow/orderflow, CFTC/TFF, market-plumbing, gap/overnight, or prior-level families.
- External-data gates remain unchanged: the longer ES+MES `trades` cache and ES `tbbo` liquidity cache are missing; no paid data was pulled.
- Verification: active sweep found `24` campaigns, `120` source variants, `120` rescue configs, `258` raw variant-level reports, `0` passes, and no active variants missing `rescue1`.


## ES/NQ Cross-Index Lead-Lag - 2026-06-16

Decision: FAIL.

- User-supplied Edge 5 was eligible as a local active-only campaign because full RTH ES and NQ Sierra order-flow caches exist and no active ES/NQ lead-lag campaign existed outside `_archived`.
- Created `campaigns/es_nq_cross_index_lead_lag/campaign.yaml` and exactly five variants using `es_nq_lead_lag`, `percent_from_entry`, and `fixed_r`.
- Built `data/cache/orderflow/es_nq_lead_lag_1m_20110103_20260609_full_rth_ny.parquet` from local ES/NQ caches; the builder aligned `1,484,730` shared minute bars and computes completed-window ES/NQ returns without future bars.
- Originals: all five failed `limited_core_grid_test` with `0.0` profitable-combo rate and zero benchmark-pass combinations. Best original was `morning_nq_down_es_lag_short_1000/run1` with top net `-273.75`, PF `0.9695833333333334`, and `96` top-combo trades.
- Rescues: all five one-time parameter-space rescues completed and failed `limited_core_grid_test`. Best rescue was `afternoon_nq_confirmed_follow_1400/rescue1` with profitable-combo rate `0.037037037037037035`, zero benchmark-pass combinations, top net `868.75`, PF `1.1387225548902196`, and `60` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_es_nq_lead_lag.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS; `python3 -m research.preflight --skip-tests` PASS with `393` active configs. Active sweep found `25` active campaigns, `125` source variants, `125` rescue configs, `268` raw variant-level reports, `0` passes, and no active variants missing a latest original or `rescue1` report.


## ES FOMC Pre-Announcement Drift - 2026-06-16

Decision: FAIL.

- User-supplied Edge 3/4/5 review left a local, active-only non-duplicate event edge: scheduled-FOMC pre-announcement drift. The campaign used official Federal Reserve scheduled decision dates and local ES Sierra RTH data.
- Created `campaigns/es_fomc_pre_announcement_drift/campaign.yaml` and exactly five variants using `fomc_pre_announcement_drift`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/fomc_scheduled_decision_dates_20110101_20260609.csv` with `122` scheduled FOMC decision dates from `2011-01-26` through `2026-04-29`; unscheduled meetings, cancelled meetings, notation votes, and conference calls were excluded.
- Originals: all five failed. Best original was `decision_day_open_long_1000/run1` with profitable-combo rate `0.5555555555555556`, top net `238.75`, PF `1.2405541561712847`, and only `11` top-combo trades in the first 18-month core window.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed. `decision_day_open_long_1000/rescue1` passed the core profitable-combo gate at `0.75` but failed `limited_monkey_test` with `percentage_profitable=0.33666666666666667`, `median_net_profit=-298.75`, stress profitability `0.6166666666666667`, and one-tick-worse net `-80.0`. The other rescues failed `limited_core_grid_test`.
- No run reached WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_fomc_pre_announcement_drift.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS. Active sweep after aggregation found `26` active campaigns, `130` source variants, `130` rescue configs, `278` raw variant-level reports, `0` passes, and no active variants missing a latest original or `rescue1` report.


## ES Volatility-Managed Intraday Premium - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_volatility_managed_intraday_premium/campaign.yaml` and exactly five variants using `volatility_managed_intraday_premium`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/es_lagged_volatility_features_20110103_20260609.csv` from the local ES Sierra RTH cache. The feature builder shifts every realized-volatility, range, absolute-return, downside-semivolatility, and volatility-ratio feature one RTH session, so current-session range/high/low/close cannot enter the signal state.
- Originals: all five failed before WFA. Best original was `low_10d_range_midmorning_long_1030/run1` with profitable-combo rate `0.5185185185185185`, benchmark pass rate `0.18518518518518517`, top net `3055.0`, PF `1.2919254658385093`, and `99` top-combo trades.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed. `low_10d_range_midmorning_long_1030/rescue1` passed core with profitable-combo rate `0.7222222222222222`, but failed `limited_monkey_test` with `percentage_profitable=0.24` and `median_net_profit=-2081.25`. Actual trade-path stress passed, including one-tick-worse net `532.5`, but the required random-placebo monkey gate failed.
- No run reached WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_volatility_managed_intraday_premium.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS. Active sweep after aggregation found `27` active campaigns, `135` source variants, `135` rescue configs, `288` raw variant-level reports, `0` passes, and no active variants missing a latest original or `rescue1` report.


## ES Halloween Seasonal Premium - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_halloween_seasonal_premium/campaign.yaml` and exactly five variants using `halloween_seasonal_premium`, `percent_from_entry`, and `fixed_r`.
- Duplicate-edge scope was active-only and ignored `_archived`. This half-year seasonal effect is distinct from active day-of-week, turn-of-month, FOMC, volatility-state, and unconditional RTH premium families.
- Originals: all five failed `limited_core_grid_test`. Best original was `winter_midday_long_1200/run1` with profitable-combo rate `0.1111111111111111`, top net `475.0`, PF `1.026319434824768`, and best-day concentration `0.8578947368421053`.
- Rescues: all five one-time stop/target rescues completed and failed `limited_core_grid_test`. Best rescue was `winter_midday_long_1200/rescue1` with profitable-combo rate `0.5`, zero benchmark-passing combinations, top net `1000.0`, PF `1.0526870389884089`, MAR `0.22386592295394953`, and best-day concentration `0.77`.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_halloween_seasonal_premium.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS. Active sweep after aggregation found `28` active campaigns, `140` source variants, `140` rescue configs, `298` raw variant-level reports, `0` passes, and no active variants missing a latest original or `rescue1` report.


## ES Quarterly Expiration Pressure - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_quarterly_expiration_pressure/campaign.yaml` and exactly five variants using `quarterly_expiration_pressure`, `percent_from_entry`, and `fixed_r`.
- Duplicate-edge scope was active-only and ignored `_archived`. This deterministic quarterly expiration/roll-calendar edge is distinct from day-of-week, turn-of-month, FOMC, Halloween, volatility-state, and unconditional RTH premium families.
- Originals: all five failed before WFA. Best original was `monday_after_expiration_reversal_long_1000/run1` with profitable-combo rate `0.6666666666666666`, zero benchmark-passing combinations, top net `895.0`, PF `4.008403361344538`, and only `6` top-combo trades.
- Rescues: all five one-time stop/target rescues completed. `monday_after_expiration_reversal_long_1000/rescue1` passed the core profitable-combo gate at `1.0`, but failed `limited_monkey_test` with `percentage_profitable=0.47` and `median_net_profit=-30.0`. Its actual trade-path stress stayed profitable, including one-tick-worse net `576.25`, but the required random-placebo monkey gate failed.
- No run reached WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_quarterly_expiration_pressure.py` PASS; targeted preflight for five rescues PASS; `python3 -m research.preflight --skip-tests` PASS with `453` configs checked. Active sweep after aggregation found `29` active campaigns, `145` source variants, `145` rescue configs, `308` raw variant-level reports, `0` passes, and no active variants missing a latest original or `rescue1` report.


## ES Pre-Holiday Effect - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_preholiday_effect/campaign.yaml` and exactly five variants using `preholiday_effect`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/nyse_preholiday_regular_sessions_20110103_20260609.csv` with `143` deterministic last-regular-session-before-full-NYSE-holiday rows. Early-close sessions are excluded to match the validated local RTH cache.
- Duplicate-edge scope was active-only and ignored `_archived`. This is distinct from day-of-week, turn-of-month, Halloween, FOMC, quarterly expiration, and unconditional RTH premium families because it conditions on full exchange holidays.
- Originals: all five failed `limited_core_grid_test`. Best original was `preholiday_late_long_1500/run1` with profitable-combo rate `0.3333333333333333`, zero benchmark-passing combinations, top net `88.125`, PF `1.235`, and best-day concentration `1.75177304964539`.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed and failed `limited_core_grid_test`. Best rescue was `preholiday_momentum_confirmed_midday_long_1200/rescue1` with profitable-combo rate `0.5`, zero benchmark-passing combinations, top net `232.5`, PF `2.2567567567567566`, and only `6` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_preholiday_effect.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS; `python3 -m research.preflight --skip-tests` PASS with `468` configs checked. Active sweep after aggregation found `30` active campaigns, `150` source variants, `150` rescue configs, `318` raw variant-level reports, `0` passes, and no active variants missing a latest original or `rescue1` report.


## ES Turn-of-Year Effect - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_turn_of_year_effect/campaign.yaml` and exactly five variants using `turn_of_year_effect`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/nyse_turn_of_year_sessions_20110103_20260609.csv` with `107` deterministic turn-of-year rows covering the last five regular December sessions and first two regular January sessions. Early-close sessions are excluded to match the validated local RTH cache.
- Duplicate-edge scope was active-only and ignored `_archived`. This is distinct from active failed all-month turn-of-month, Halloween, pre-holiday, FOMC, quarterly-expiration, and unconditional RTH premium families because it tests the annual Christmas/New-Year window.
- Originals: all five failed `limited_core_grid_test`. Best original was `january_first2_open_long_1000/run1` with profitable-combo rate `0.3333333333333333`, zero benchmark-passing combinations, top net `222.5`, PF `2.435483870967742`, and only `3` top-combo trades.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed and failed `limited_core_grid_test`. Best rescue was `january_first2_open_long_1000/rescue1` with profitable-combo rate `0.4166666666666667`, zero benchmark-passing combinations, top net `222.5`, PF `2.435483870967742`, and only `3` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_turn_of_year_effect.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS; `python3 -m research.preflight --skip-tests` PASS with `483` configs checked. Active sweep after aggregation found `31` active campaigns, `155` source variants, `155` rescue configs, `328` raw variant-level reports, `0` passes, and no active variants missing a latest original or `rescue1` report.


## ES BLS Macro Release-Day Drift - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_bls_macro_release_day_drift/campaign.yaml` and exactly five variants using `bls_macro_release_day_drift`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/bls_macro_release_dates_20110103_20260609.csv` from ALFRED/FRED BLS release-date downloads. It contains `386` rows: `190` Employment Situation releases and `196` CPI releases. The release date is known before RTH; release values, revisions, and surprises are not used.
- Duplicate-edge scope was active-only and ignored `_archived`. This is distinct from active FOMC pre-announcement drift because it conditions on BLS 08:30 ET CPI/Employment Situation dates and tests only post-release RTH behavior.
- Originals: all five failed `limited_core_grid_test`. Best original was `employment_release_open_long_1000/run1` with profitable-combo rate `0.4444444444444444`, zero benchmark-passing combinations, top net `427.5`, PF `1.3949191685912241`, and only `17` top-combo trades.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed and failed `limited_core_grid_test`. Best rescue was `employment_release_open_long_1000/rescue1` with profitable-combo rate `0.5833333333333334`, zero benchmark-passing combinations, top net `465.0`, PF `1.382716049382716`, and only `17` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_bls_macro_release_day_drift.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS; `python3 -m research.preflight --skip-tests` PASS with `498` configs checked. Active sweep after aggregation found `32` active campaigns, `160` source variants, `160` rescue configs, `338` raw variant-level reports, `0` passes, and no active variants missing a latest original or `rescue1` report.


## ES Term-Structure Lead-Lag Feedback - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_term_structure_lead_lag_feedback/campaign.yaml` and exactly five variants using `es_term_structure_lead_lag`, `percent_from_entry`, and `fixed_r`.
- Built `data/cache/orderflow/es_term_structure_lead_lag_1m_20110311_20260316_full_rth_ny.parquet` from local ES front-contract cache, raw Sierra contract files, and the explicit ES roll calendar. The builder uses the next explicit roll-calendar contract as deferred, not same-day volume, and computes rolling front/deferred return gaps from completed current-or-prior minutes only.
- Cache validation: `111930` rows, `287` aligned RTH sessions, first timestamp `2011-03-11 09:30:00`, last timestamp `2026-03-16 15:59:00`, no duplicate timestamps, no invalid OHLC rows, and missing deferred file `ESU26`.
- Originals: all five failed `limited_core_grid_test`. Best original was `late_morning_two_sided_spread_feedback_1130/run1` with profitable-combo rate `0.48148148148148145`, zero benchmark-passing combinations, top net `342.5`, PF `69.5`, and only `4` top-combo trades.
- Rescues: all five one-time parameter-space rescues completed and failed `limited_core_grid_test`. Best rescue was `late_day_two_sided_spread_feedback_1530/rescue1` with profitable-combo rate `0.2222222222222222`, zero benchmark-passing combinations, top net `100.0`, and only `5` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_es_term_structure_lead_lag.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS; `python3 -m research.preflight --skip-tests` PASS with `513` configs checked. Active sweep after aggregation found `33` active campaigns, `165` source variants, `165` rescue configs, `348` raw variant-level reports, `0` passes, and no active variants missing any original run or `rescue1` report.


## ES Monthly OPEX Pressure - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_monthly_opex_pressure/campaign.yaml` and exactly five variants using `monthly_opex_pressure`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/nyse_monthly_opex_sessions_20110103_20260609.csv` with `555` deterministic monthly OPEX signal rows: `124` non-quarterly rows each for previous regular session, OPEX session, and next regular session, plus `61` quarterly rows for each signal type. All strategy configs set `include_quarterly_months: false`.
- Duplicate-edge scope was active-only and ignored `_archived`. This edge is distinct from active failed `es_quarterly_expiration_pressure` because it excludes March, June, September, and December and tests non-quarterly monthly listed-option expiration/pinning/unwind pressure rather than quarterly futures roll and quarterly expiration mechanics.
- Originals: all five failed `limited_core_grid_test`. Best original was `nonquarterly_opex_thursday_positioning_short_1330/run1` with profitable-combo rate `0.5555555555555556`, zero benchmark-passing combinations, top net `740.0`, PF `2.0033898305084747`, and only `12` top-combo trades.
- Rescues: all five one-time stop/target parameter-space rescues completed and failed `limited_core_grid_test`. Best rescue was `nonquarterly_opex_thursday_positioning_short_1330/rescue1` with profitable-combo rate `0.5833333333333334`, zero benchmark-passing combinations, top net `830.625`, PF `2.1536458333333335`, and only `12` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_monthly_opex_pressure.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS; `python3 -m research.preflight --skip-tests` PASS with `528` configs checked. Active sweep after aggregation found `34` active campaigns, `170` source variants, `170` rescue configs, `358` raw variant-level reports, `0` passes, and no active variants missing any original run or `rescue1` report.


## ES VIX Expiration Pressure - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_vix_expiration_pressure/campaign.yaml` and exactly five variants using `vix_expiration_pressure`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/vix_expiration_sessions_20110103_20260609.csv` with `555` deterministic signal rows covering previous regular session, VIX expiration session, and next regular session. The calendar applies the monthly VIX standard expiration rule against the following-month SPX standard expiration session, with holiday/early-close shifts handled before testing.
- Duplicate-edge scope was active-only and ignored `_archived`. This edge is distinct from monthly and quarterly OPEX campaigns because it tests VIX derivatives settlement/SOQ pressure rather than equity/index listed-option expiration or ES quarterly roll pressure.
- Originals: all five failed `limited_core_grid_test`. Best original was `vix_settlement_open_pressure_short_1000/run1` with profitable-combo rate `0.6666666666666666`, zero benchmark-passing combinations, top net `1040.0`, PF `1.4952380952380953`, and only `17` top-combo trades.
- Rescues: all five one-time stop/target parameter-space rescues completed and failed `limited_core_grid_test`. Best rescue was `vix_settlement_open_pressure_short_1000/rescue1` with profitable-combo rate `0.5833333333333334`, zero benchmark-passing combinations, top net `2208.75`, PF `2.2004076086956523`, and only `17` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_vix_expiration_pressure.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS; `python3 -m research.preflight --skip-tests` PASS with `543` configs checked. Active sweep after aggregation found `35` active campaigns, `175` source variants, `175` rescue configs, `368` raw variant-level reports, `0` passes, and no active variants missing any original run or `rescue1` report.
