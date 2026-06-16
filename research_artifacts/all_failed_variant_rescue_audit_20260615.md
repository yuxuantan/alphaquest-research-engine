# All Failed Variant Rescue Audit

Date: 2026-06-15

Decision: FAIL

## Scope

The user clarified that each failed variant can receive one rescue run. This audit records the resulting per-variant rescue coverage across the active ES campaigns. A rescue may change only existing fixed parameters or tunable parameter space inside existing modules; it may not change the core strategy mechanic, modules, timeframe, data window, costs, fill assumptions, or validation gates.

## Coverage

- Active variant configs checked: 85
- Rescue configs present: 85
- Active variants missing `rescue1` report: 0
- Rescue reports with `passed=true`: 0
- Final decision from rescue coverage: FAIL

## Verification Commands

```bash
python3 -m research.preflight --skip-tests
for cfg in campaigns/*/rescue_attempts/parameter_space_rescue_1/*/config.yaml; do python3 -m research.preflight --config "$cfg" --skip-tests; done
python3 -m propstack.run_campaign_stages --config <missing_rescue_config.yaml> --fast-runtime-defaults
```

Preflight results: repo-wide preflight passed with 268 active configs after the
CFTC/TFF hedging-pressure campaign was added; targeted preflight passed for
the five new CFTC/TFF hedging-pressure rescue configs and the staged rescue
runs completed. The active report sweep found 188 raw variant-level reports,
zero passes, 85 latest original reports, 85 `rescue1` reports, and zero active
variants missing `rescue1`. The earlier staged loop ran the 23
previously missing `rescue1` reports and skipped no existing reports. Existing
`rescue1` reports were retained and not rerun.

## Rescue Results

| Campaign | Variant | TF | Combos | Terminal stage | Profitable/monkey pct | Median | Top net | Top PF | Top trades | Failure gate |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `es_connors_rsi2_mean_reversion` | `fifteen_min_long_uptrend_pullback_1545` | 15m | 81 | `limited_core_grid_test` | 0.345679012345679 |  | 2646.25 | 1.2806203605514317 | 92 | summary.percentage_profitable_iterations=0.345679012345679 |
| `es_connors_rsi2_mean_reversion` | `fifteen_min_short_downtrend_bounce_1545` | 15m | 81 | `limited_core_grid_test` | 0.0 |  | -1432.5 | 0.33603707995365006 | 19 | summary.percentage_profitable_iterations=0.0 |
| `es_connors_rsi2_mean_reversion` | `five_min_long_vwap_extreme_1430` | 5m | 81 | `limited_core_grid_test` | 0.012345679012345678 |  | 427.5 | 1.0337677725118484 | 87 | summary.percentage_profitable_iterations=0.012345679012345678 |
| `es_connors_rsi2_mean_reversion` | `five_min_short_vwap_extreme_1430` | 5m | 81 | `limited_core_grid_test` | 0.19753086419753085 |  | 3805.0 | 1.6085565773690524 | 49 | summary.percentage_profitable_iterations=0.19753086419753085 |
| `es_connors_rsi2_mean_reversion` | `thirty_min_two_sided_trend_reversion_1530` | 30m | 81 | `limited_core_grid_test` | 0.24691358024691357 |  | 2465.0 | 1.3281198003327788 | 77 | summary.percentage_profitable_iterations=0.24691358024691357 |
| `es_mes_micro_flow_divergence_reversion` | `afternoon_mes_large20_buy_pressure_short` | 1m | 36 | `limited_monkey_test` | 0.36666666666666664 | -1901.25 |  |  |  | summary.percentage_profitable=0.36666666666666664; summary.median_net_profit=-1901.25 |
| `es_mes_micro_flow_divergence_reversion` | `afternoon_mes_large20_sell_pressure_long` | 1m | 36 | `limited_monkey_test` | 0.43 | -1723.75 |  |  |  | summary.percentage_profitable=0.43; summary.median_net_profit=-1723.75; summary.trade_path_stress.percentage_profitable=0.4866666666666667; summary.trade_path_stress.median_net_profit=-73.21438022763687; summary.trade_path_stress.one_tick_worse.profitable=False |
| `es_mes_micro_flow_divergence_reversion` | `midday_mes_price_richness_fade` | 1m | 36 | `limited_monkey_test` | 0.38666666666666666 | -5822.5 |  |  |  | summary.percentage_profitable=0.38666666666666666; summary.median_net_profit=-5822.5 |
| `es_mes_micro_flow_divergence_reversion` | `morning_mes_buy_pressure_reversion_short` | 1m | 36 | `limited_monkey_test` | 0.36 | -2702.5 |  |  |  | summary.percentage_profitable=0.36; summary.median_net_profit=-2702.5 |
| `es_mes_micro_flow_divergence_reversion` | `morning_mes_sell_pressure_reversion_long` | 1m | 36 | `limited_monkey_test` | 0.47 | -800.0 |  |  |  | summary.percentage_profitable=0.47; summary.median_net_profit=-800.0 |
| `es_overnight_intraday_reversal` | `first15_confirm_reversal_1000` | 5m | 81 | `limited_core_grid_test` | 0.16049382716049382 |  | 1403.75 | 1.1076082790341126 | 83 | summary.percentage_profitable_iterations=0.16049382716049382 |
| `es_overnight_intraday_reversal` | `first30_noncontinuation_1000` | 5m | 81 | `limited_core_grid_test` | 0.0 |  | -1040.0 | 0.9241152863918278 | 83 | summary.percentage_profitable_iterations=0.0 |
| `es_overnight_intraday_reversal` | `first5_confirm_reversal_1000` | 5m | 81 | `limited_core_grid_test` | 0.0 |  | -826.25 | 0.9484318926509596 | 94 | summary.percentage_profitable_iterations=0.0 |
| `es_overnight_intraday_reversal` | `high_overnight_first15_short_1000` | 5m | 81 | `limited_core_grid_test` | 0.691358024691358 |  | 3842.5 | 1.4204048140043763 | 54 | summary.percentage_profitable_iterations=0.691358024691358 |
| `es_overnight_intraday_reversal` | `low_overnight_first15_long_1000` | 5m | 81 | `limited_core_grid_test` | 0.04938271604938271 |  | 677.5 | 1.090878604963112 | 52 | summary.percentage_profitable_iterations=0.04938271604938271 |
| `es_prior_session_ibs_reversion` | `delayed_high_ibs_short_range_filtered` | 5m | 81 | `limited_core_grid_test` | 0.5061728395061729 |  | 4650.0 | 2.1390079608083283 | 30 | summary.percentage_profitable_iterations=0.5061728395061729 |
| `es_prior_session_ibs_reversion` | `delayed_low_ibs_long_range_filtered` | 5m | 81 | `limited_core_grid_test` | 0.43209876543209874 |  | 1512.5 | 1.5321020228671944 | 30 | summary.percentage_profitable_iterations=0.43209876543209874 |
| `es_prior_session_ibs_reversion` | `open_high_ibs_short` | 5m | 81 | `limited_core_grid_test` | 0.345679012345679 |  | 1617.5 | 1.314535731648031 | 29 | summary.percentage_profitable_iterations=0.345679012345679 |
| `es_prior_session_ibs_reversion` | `open_low_ibs_long` | 5m | 81 | `limited_core_grid_test` | 0.0 |  | -227.5 | 0.9029850746268657 | 18 | summary.percentage_profitable_iterations=0.0 |
| `es_prior_session_ibs_reversion` | `open_two_sided_ibs_reversion` | 5m | 81 | `limited_core_grid_test` | 0.024691358024691357 |  | 127.5 | 1.027027027027027 | 47 | summary.percentage_profitable_iterations=0.024691358024691357 |
| `es_range_compression_breakout` | `id_nr4_prior_session_breakout` | 5m | 81 | `limited_monkey_test` | 0.2866666666666667 | -548.75 |  |  |  | summary.percentage_profitable=0.2866666666666667; summary.median_net_profit=-548.75 |
| `es_range_compression_breakout` | `nr4_prior_session_breakout` | 5m | 81 | `limited_core_grid_test` | 0.4074074074074074 |  | 1542.5 | 1.0915837910048982 | 114 | summary.percentage_profitable_iterations=0.4074074074074074 |
| `es_range_compression_breakout` | `nr7_opening_range_15_long_breakout` | 5m | 81 | `limited_core_grid_test` | 0.4074074074074074 |  | 1290.0 | 1.3091671659676454 | 42 | summary.percentage_profitable_iterations=0.4074074074074074 |
| `es_range_compression_breakout` | `nr7_opening_range_15_short_breakout` | 5m | 81 | `limited_core_grid_test` | 0.0 |  | -882.5 | 0.8127320954907162 | 34 | summary.percentage_profitable_iterations=0.0 |
| `es_range_compression_breakout` | `nr7_opening_range_30_breakout` | 5m | 81 | `limited_core_grid_test` | 0.07407407407407407 |  | 192.5 | 1.0271796681962584 | 64 | summary.percentage_profitable_iterations=0.07407407407407407 |
| `es_rth_intraday_risk_premium` | `early_afternoon_1300_long` | 5m | 9 | `limited_core_grid_test` | 0.0 |  | -6197.5 | 0.8114828897338403 | 362 | summary.percentage_profitable_iterations=0.0 |
| `es_rth_intraday_risk_premium` | `first_hour_1000_long` | 5m | 9 | `limited_core_grid_test` | 0.0 |  | -7102.5 | 0.8570925553319919 | 363 | summary.percentage_profitable_iterations=0.0 |
| `es_rth_intraday_risk_premium` | `late_morning_1100_long` | 5m | 9 | `limited_core_grid_test` | 0.0 |  | -2302.5 | 0.9468704932218056 | 363 | summary.percentage_profitable_iterations=0.0 |
| `es_rth_intraday_risk_premium` | `midmorning_1030_long` | 5m | 9 | `limited_core_grid_test` | 0.0 |  | -8702.5 | 0.8168376742962379 | 363 | summary.percentage_profitable_iterations=0.0 |
| `es_rth_intraday_risk_premium` | `open_0935_long` | 5m | 9 | `limited_core_grid_test` | 0.0 |  | -7085.0 | 0.8905537962462347 | 362 | summary.percentage_profitable_iterations=0.0 |
| `es_signed_orderflow_persistence` | `early_5m_signed_flow_continuation_1000` | 1m | 81 | `limited_core_grid_test` | 0.1111111111111111 |  | 728.75 | 1.0471453986737829 | 198 | summary.percentage_profitable_iterations=0.1111111111111111 |
| `es_signed_orderflow_persistence` | `late_morning_15m_signed_flow_continuation_1130` | 1m | 81 | `limited_core_grid_test` | 0.012345679012345678 |  | 90.625 | 1.0156587473002159 | 70 | summary.percentage_profitable_iterations=0.012345679012345678 |
| `es_signed_orderflow_persistence` | `midday_30m_signed_flow_continuation_1230` | 1m | 81 | `limited_core_grid_test` | 0.0 |  | -3063.75 | 0.801281011837198 | 179 | summary.percentage_profitable_iterations=0.0 |
| `es_signed_orderflow_persistence` | `afternoon_60m_signed_flow_continuation_1400` | 1m | 81 | `limited_core_grid_test` | 0.0 |  | -1038.75 | 0.931480870712401 | 149 | summary.percentage_profitable_iterations=0.0 |
| `es_signed_orderflow_persistence` | `late_large20_30m_flow_continuation_1500` | 1m | 81 | `limited_core_grid_test` | 0.0 |  | -212.5 | 0.9713708319299428 | 95 | summary.percentage_profitable_iterations=0.0 |
| `es_opening_drive_inventory_absorption` | `open30_flow_continuation_1030` | 1m | 81 | `limited_core_grid_test` | 0.35802469135802467 |  | 791.25 | 2.276209677419355 | 13 | summary.percentage_profitable_iterations=0.35802469135802467 |
| `es_opening_drive_inventory_absorption` | `open60_flow_continuation_1130` | 1m | 81 | `limited_monkey_test` | 0.20666666666666667 | -881.25 | 587.5 |  | 25 | summary.percentage_profitable=0.20666666666666667; summary.trade_path_stress.percentage_profitable=0.5866666666666667; summary.trade_path_stress.one_tick_worse.profitable=False |
| `es_opening_drive_inventory_absorption` | `open30_absorbed_pressure_fade_1015` | 1m | 81 | `limited_core_grid_test` | 0.0 |  | -295.0 | 0.8262150220913107 | 24 | summary.percentage_profitable_iterations=0.0 |
| `es_opening_drive_inventory_absorption` | `open60_exhaustion_fade_1300` | 1m | 81 | `limited_core_grid_test` | 0.4074074074074074 |  | 299.375 | 1.6472972972972972 | 12 | summary.percentage_profitable_iterations=0.4074074074074074 |
| `es_opening_drive_inventory_absorption` | `open30_price_flow_divergence_fade_1400` | 1m | 81 | `limited_core_grid_test` | 0.0 |  | -117.5 | 0.8715846994535519 | 21 | summary.percentage_profitable_iterations=0.0 |
| `es_turn_of_month_seasonality` | `classic_turn_window_1000_long` | 5m | 81 | `limited_core_grid_test` | 0.0 |  | -96.25 | 0.9914501443482123 | 73 | summary.percentage_profitable_iterations=0.0 |
| `es_turn_of_month_seasonality` | `early_month_first_days_1000_long` | 5m | 27 | `limited_core_grid_test` | 0.07407407407407407 |  | 178.75 | 1.0998603351955307 | 13 | summary.percentage_profitable_iterations=0.07407407407407407 |
| `es_turn_of_month_seasonality` | `month_end_last_days_1000_long` | 5m | 27 | `limited_core_grid_test` | 0.0 |  | -206.25 | 0.9775326797385621 | 60 | summary.percentage_profitable_iterations=0.0 |
| `es_turn_of_month_seasonality` | `opening_turn_window_0935_long` | 5m | 81 | `limited_core_grid_test` | 0.07407407407407407 |  | 1685.0 | 1.247248716067498 | 73 | summary.percentage_profitable_iterations=0.07407407407407407 |
| `es_turn_of_month_seasonality` | `late_turn_window_1300_long` | 5m | 81 | `limited_core_grid_test` | 0.0 |  | -352.5 | 0.95425048669695 | 73 | summary.percentage_profitable_iterations=0.0 |
| `es_daily_time_series_momentum` | `long_only_trend_1000` | 5m | 81 | `limited_core_grid_test` | 0.2839506172839506 |  | 2822.5 | 1.1703636637996078 | 123 | summary.percentage_profitable_iterations=0.2839506172839506 |
| `es_daily_time_series_momentum` | `short_term_alignment_1000_two_sided` | 5m | 81 | `limited_core_grid_test` | 0.0 |  | -3692.5 | 0.5051926298157454 | 121 | summary.percentage_profitable_iterations=0.0 |
| `es_daily_time_series_momentum` | `sixty_day_trend_1000_two_sided` | 5m | 81 | `limited_core_grid_test` | 0.19753086419753085 |  | 2822.5 | 1.1703636637996078 | 123 | summary.percentage_profitable_iterations=0.19753086419753085 |
| `es_daily_time_series_momentum` | `twenty_day_trend_1000_two_sided` | 5m | 81 | `limited_core_grid_test` | 0.0 |  | -7776.25 | 0.8003786420228469 | 354 | summary.percentage_profitable_iterations=0.0 |
| `es_daily_time_series_momentum` | `vol_norm_trend_1000_two_sided` | 5m | 81 | `limited_core_grid_test` | 0.14814814814814814 |  | 1392.5 | 1.104542042042042 | 89 | summary.percentage_profitable_iterations=0.14814814814814814 |
| `es_late_day_intraday_momentum` | `first30_to_last30_two_sided` | 5m | 27 | `limited_core_grid_test` | 0.0 |  | -2941.25 | 0.07942097026604068 | 72 | summary.percentage_profitable_iterations=0.0 |
| `es_late_day_intraday_momentum` | `first30_to_last30_long_only` | 5m | 27 | `limited_core_grid_test` | 0.0 |  | -742.5 | 0.7933194154488518 | 76 | summary.percentage_profitable_iterations=0.0 |
| `es_late_day_intraday_momentum` | `first30_volume_range_conditioned` | 5m | 81 | `limited_core_grid_test` | 0.0 |  | -912.5 | 0.4296875 | 35 | summary.percentage_profitable_iterations=0.0 |
| `es_late_day_intraday_momentum` | `first60_to_last30_two_sided` | 5m | 27 | `limited_core_grid_test` | 0.0 |  | -2316.25 | 0.08267326732673268 | 57 | summary.percentage_profitable_iterations=0.0 |
| `es_late_day_intraday_momentum` | `first30_penultimate_alignment` | 5m | 81 | `limited_core_grid_test` | 0.0 |  | -240.0 | 0.1111111111111111 | 8 | summary.percentage_profitable_iterations=0.0 |
| `es_volume_shock_liquidity_reversal` | `all_day_symmetric_shock_reversion` | 5m | 81 | `limited_core_grid_test` | 0.024691358024691357 |  | 397.5 | 1.1079429735234216 | 33 | summary.percentage_profitable_iterations=0.024691358024691357 |
| `es_volume_shock_liquidity_reversal` | `morning_down_shock_reversal_long` | 5m | 81 | `limited_core_grid_test` | 0.1728395061728395 |  | 1257.5 | 2.3933518005540164 | 11 | summary.percentage_profitable_iterations=0.1728395061728395 |
| `es_volume_shock_liquidity_reversal` | `morning_up_shock_reversal_short` | 5m | 81 | `limited_core_grid_test` | 0.08641975308641975 |  | 2167.5 | 1.3681528662420381 | 29 | summary.percentage_profitable_iterations=0.08641975308641975 |
| `es_volume_shock_liquidity_reversal` | `midday_symmetric_shock_reversion` | 5m | 81 | `limited_core_grid_test` | 0.20987654320987653 |  | 1866.25 | 3.2759146341463414 | 13 | summary.percentage_profitable_iterations=0.20987654320987653 |
| `es_volume_shock_liquidity_reversal` | `afternoon_symmetric_shock_reversion` | 5m | 81 | `limited_core_grid_test` | 0.06172839506172839 |  | 1770.0 | 1.386252045826514 | 36 | summary.percentage_profitable_iterations=0.06172839506172839 |
| `es_prior_day_stop_run_reclaim` | `full_session_two_sided_reclaim` | 5m | 81 | `limited_core_grid_test` | 0.2716049382716049 |  | 880.0 | 1.188034188034188 | 54 | summary.percentage_profitable_iterations=0.2716049382716049 |
| `es_prior_day_stop_run_reclaim` | `morning_prior_low_reclaim_long` | 5m | 81 | `limited_core_grid_test` | 0.654320987654321 |  | 1803.75 | 2.276991150442478 | 23 | summary.percentage_profitable_iterations=0.654320987654321 |
| `es_prior_day_stop_run_reclaim` | `morning_prior_high_reject_short` | 5m | 81 | `limited_monkey_test` | 0.32666666666666666 | -770.0 | 2673.75 | 2.0813953488372094 | 24 | summary.percentage_profitable=0.32666666666666666; summary.median_net_profit=-770.0 |
| `es_prior_day_stop_run_reclaim` | `midday_two_sided_reclaim` | 5m | 81 | `limited_core_grid_test` | 0.2222222222222222 |  | 763.75 | 1.8728571428571428 | 11 | summary.percentage_profitable_iterations=0.2222222222222222 |
| `es_prior_day_stop_run_reclaim` | `afternoon_two_sided_reclaim` | 5m | 81 | `limited_core_grid_test` | 0.345679012345679 |  | 933.75 | 2.8863636363636362 | 17 | summary.percentage_profitable_iterations=0.345679012345679 |
| `es_vwap_pullback_continuation` | `failed_vwap_break_two_sided` | 5m | 81 | `limited_core_grid_test` | 0.24691358024691357 |  | 2180.0 | 2.768762677484787 | 9 | summary.percentage_profitable_iterations=0.24691358024691357 |
| `es_vwap_pullback_continuation` | `midday_trend_reclaim_two_sided` | 5m | 81 | `limited_monkey_test` | 0.18 | -3210.0 | 3392.5 | 1.3551426328186338 | 89 | summary.percentage_profitable=0.18; summary.median_net_profit=-3210.0 |
| `es_vwap_pullback_continuation` | `morning_opening_drive_pullback_long` | 5m | 81 | `limited_core_grid_test` | 0.14814814814814814 |  | 1807.5 | 1.2726244343891402 | 51 | summary.percentage_profitable_iterations=0.14814814814814814 |
| `es_vwap_pullback_continuation` | `morning_opening_drive_pullback_short` | 5m | 81 | `limited_core_grid_test` | 0.2345679012345679 |  | 1988.125 | 1.2218270571827057 | 58 | summary.percentage_profitable_iterations=0.2345679012345679 |
| `es_vwap_pullback_continuation` | `morning_trend_reclaim_two_sided` | 5m | 81 | `limited_core_grid_test` | 0.1111111111111111 |  | 725.0 | 1.3148751357220412 | 35 | summary.percentage_profitable_iterations=0.1111111111111111 |
| `es_cftc_tff_hedging_pressure` | `broad_negative_pressure_short_1100` | 5m | 27 | `limited_core_grid_test` | 0.0 |  | -1208.75 | 0.9263855054811205 | 103 | summary.percentage_profitable_iterations=0.0 |
| `es_cftc_tff_hedging_pressure` | `broad_positive_pressure_long_1100` | 5m | 27 | `limited_core_grid_test` | 0.0 |  | -2465.0 | 0.7045250224752772 | 58 | summary.percentage_profitable_iterations=0.0 |
| `es_cftc_tff_hedging_pressure` | `extreme_negative_pressure_short_1330` | 5m | 27 | `limited_core_grid_test` | 0.18518518518518517 |  | 262.5 | 1.5706521739130435 | 5 | summary.percentage_profitable_iterations=0.18518518518518517 |
| `es_cftc_tff_hedging_pressure` | `extreme_positive_pressure_long_1330` | 5m | 27 | `limited_core_grid_test` | 0.3333333333333333 |  | 775.0 | 4.924050632911392 | 5 | summary.percentage_profitable_iterations=0.3333333333333333 |
| `es_cftc_tff_hedging_pressure` | `high_positive_pressure_long_0935` | 5m | 27 | `limited_core_grid_test` | 0.1111111111111111 |  | 915.625 |  | 5 | summary.percentage_profitable_iterations=0.1111111111111111 |

## Conclusion

Every active failed ES variant now has exactly one `rescue1` report. All rescues failed before WFA or at the limited monkey gate. No rescue produced a candidate strategy for manual chart review or paper incubation. No second rescue is permitted for any of these variants under the current rule.

The search remains fail-closed for the active campaign set. Archived tests are
ignored for duplicate-edge checks; see
`research_artifacts/duplicate_edge_scope_policy_20260615.md`. Further progress
requires either a new edge that is not already active and has available local
data, or explicit approval for the retained external-data branches documented
in `research_artifacts/local_no_duplicate_data_gate_audit_20260615.md`.


## 2026-06-16 Market-Plumbing Rescue Update

Added `es_market_plumbing_liquidity_capacity` to active rescue coverage. Five valid originals and five one-time rescues completed. No report passed. `dealer_lending_pressure_long_1330` original and `dual_pressure_priority_long_1130` rescue reached `limited_monkey_test`; both failed the profitability/median gate. The other eight valid runs failed `limited_core_grid_test`.

Latest verification: active sweep found 188 raw variant-level reports, 0 passes, 85 latest original reports, 85 `rescue1` reports, and 0 active variants missing `rescue1`.


## 2026-06-16 Bankruptcy-Distress Rescue Update

Added `es_bankruptcy_distress_regime_reversion` to active rescue coverage. Five corrected originals and five one-time rescues completed. No report passed; all valid runs failed `limited_core_grid_test`. Latest active coverage is 85 source variants, 85 latest original reports, 85 `rescue1` reports, and 0 passes.


## 2026-06-16 Prior-Session Level Breakout Continuation Update

Added `es_prior_session_level_breakout_continuation`. All five original variants failed and all five one-time parameter-space/fixed-parameter rescues were run. Four rescues reached and failed `limited_monkey_test`; one rescue failed `limited_core_grid_test`. Active sweep after this update: 90 active source variants, 90 rescue configs, 198 raw variant-level reports, 0 passes, and 0 active variants missing `rescue1`.


## 2026-06-16 VPIN Toxicity Continuation Update

Added `es_vpin_toxicity_continuation`. All five original variants failed and all five one-time parameter-space/fixed-parameter rescues were run. Two valid runs reached and failed `limited_monkey_test`; the others failed `limited_core_grid_test`. Active sweep after this update should show 95 active source variants, 95 rescue configs, 208 raw variant-level reports, 0 passes, and 0 active variants missing `rescue1`.


## 2026-06-16 Overnight Return Late-Day Momentum Update

Added `es_overnight_return_late_day_momentum`. All five original variants failed and all five one-time parameter-space/fixed-parameter rescues were run. Every valid original and rescue failed `limited_core_grid_test` with 0.0 profitable-combo rate. Active sweep after this update should show 100 active source variants, 100 rescue configs, 218 raw variant-level reports, 0 passes, and 0 active variants missing `rescue1`.


## 2026-06-16 Prior-Level Delta Dislocation Update

Added `es_prior_level_delta_dislocation`. All five original variants failed and all five one-time parameter-space/fixed-parameter rescues were run. Every original and rescue failed `limited_core_grid_test`; no run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. Verified active sweep after this update: 105 active source variants, 105 rescue configs, 228 raw variant-level reports, 0 passes, and 0 active variants missing `rescue1`.


## 2026-06-16 Orderflow Absorption Exhaustion Reversal Update

Added `es_orderflow_absorption_exhaustion_reversal`. All five original variants failed and all five one-time parameter-space/fixed-parameter rescues were run. One original reached and failed `limited_monkey_test`; all other valid runs failed `limited_core_grid_test`.

Verified active sweep after this update: 110 active source variants, 110 rescue configs, 238 raw variant-level reports, 0 passes, and 0 active variants missing `rescue1`. `python3 -m research.preflight --skip-tests` passed with 348 configs checked.

## 2026-06-16 Day-of-Week Seasonality Update

Added `es_day_of_week_seasonality`. Archived tests were ignored for duplicate checks; the active distinction is weekday-conditioned direction, not unconditional RTH drift or monthly turn-of-month timing. All five original variants failed `limited_core_grid_test`, and all five one-time stop/target parameter-space rescues were run. Every original and rescue failed `limited_core_grid_test` with `0.0` profitable-combo rate; no run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

Latest verification after this update: `python3 -m research.preflight --skip-tests` passed with 363 configs checked; active sweep found 115 active source variants, 115 rescue configs, 248 raw variant-level reports, 0 passes, and 0 active variants missing `rescue1`.


## 2026-06-16 Overnight Inventory Sweep Reversion Update

Added `es_overnight_inventory_sweep_reversion`. All five original variants failed and all five one-time parameter-space rescues were run. One original reached and failed `limited_monkey_test`; the other nine valid original/rescue runs failed `limited_core_grid_test`. No run reached WFA, Monte Carlo, simulated incubation, or frozen validation.

Verified active sweep after this update: 120 active source variants, 120 rescue configs, 258 raw variant-level reports, 0 passes, 0 active variants missing a latest original report, and 0 active variants missing `rescue1`. `python3 -m research.preflight --skip-tests` passed with 378 configs checked.

## 2026-06-16 ES/NQ Cross-Index Lead-Lag Update

Added `es_nq_cross_index_lead_lag`. All five original variants failed `limited_core_grid_test` and all five one-time parameter-space rescues were run. Every original and rescue failed `limited_core_grid_test`; no run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

Verified active sweep after this update: 125 active source variants, 125 rescue configs, 268 raw variant-level reports, 0 passes, 0 active variants missing a latest original report, and 0 active variants missing `rescue1`. `python3 -m research.preflight --skip-tests` passed with 393 configs checked.

## 2026-06-16 FOMC Pre-Announcement Drift Update

Added `es_fomc_pre_announcement_drift`. All five original variants failed and
all five one-time parameter-space/fixed-parameter rescues were run. Four
rescues failed `limited_core_grid_test`; `decision_day_open_long_1000/rescue1`
passed core but failed `limited_monkey_test` with
`percentage_profitable=0.33666666666666667`, `median_net_profit=-298.75`,
trade-path stress profitability `0.6166666666666667`, and one-tick-worse net
profit `-80.0`.

Verified active sweep after this update: 130 active source variants, 130 rescue
configs, 278 raw variant-level reports, 0 passes, 0 active variants missing a
latest original report, and 0 active variants missing `rescue1`.

## 2026-06-16 Volatility-Managed Intraday Premium Update

Added `es_volatility_managed_intraday_premium`. All five original variants
failed and all five one-time parameter-space/fixed-parameter rescues were run.
Four rescues failed `limited_core_grid_test`; `low_10d_range_midmorning_long_1030/rescue1`
passed core but failed `limited_monkey_test` with
`percentage_profitable=0.24` and `median_net_profit=-2081.25`. Actual trade-path
stress passed, including one-tick-worse net profit `532.5`, but the required
random-placebo monkey gate failed.

Verified active sweep after this update: 135 active source variants, 135 rescue
configs, 288 raw variant-level reports, 0 passes, 0 active variants missing a
latest original report, and 0 active variants missing `rescue1`.

## 2026-06-16 Halloween Seasonal Premium Update

Added `es_halloween_seasonal_premium`. All five original variants failed and
all five one-time stop/target parameter-space rescues were run. Every original
and rescue failed `limited_core_grid_test`; no run reached monkey, WFA, Monte
Carlo, simulated incubation, or frozen validation.

Verified active sweep after this update: 140 active source variants, 140 rescue
configs, 298 raw variant-level reports, 0 passes, 0 active variants missing a
latest original report, and 0 active variants missing `rescue1`.

## 2026-06-16 Quarterly Expiration Pressure Update

Added `es_quarterly_expiration_pressure`. All five original variants failed and
all five one-time stop/target parameter-space rescues were run. Four rescues
failed `limited_core_grid_test`; `monday_after_expiration_reversal_long_1000/rescue1`
passed core but failed `limited_monkey_test` with
`percentage_profitable=0.47` and `median_net_profit=-30.0`. Actual trade-path
stress passed, including one-tick-worse net profit `576.25`, but the required
random-placebo monkey gate failed.

Verified active sweep after this update: 145 active source variants, 145 rescue
configs, 308 raw variant-level reports, 0 passes, 0 active variants missing a
latest original report, and 0 active variants missing `rescue1`.

## 2026-06-16 Pre-Holiday Effect Update

Added `es_preholiday_effect`. All five original variants failed
`limited_core_grid_test` and all five one-time parameter-space/fixed-parameter
rescues were run. Every original and rescue failed `limited_core_grid_test`; no
run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen
validation.

Verified active sweep after this update: 150 active source variants, 150 rescue
configs, 318 raw variant-level reports, 0 passes, 0 active variants missing a
latest original report, and 0 active variants missing `rescue1`.

## 2026-06-16 Turn-of-Year Effect Update

Added `es_turn_of_year_effect`. All five original variants failed
`limited_core_grid_test` and all five one-time parameter-space/fixed-parameter
rescues were run. Every original and rescue failed `limited_core_grid_test`; no
run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen
validation.

Verified active sweep after this update: 155 active source variants, 155 rescue
configs, 328 raw variant-level reports, 0 passes, 0 active variants missing a
latest original report, and 0 active variants missing `rescue1`.

## 2026-06-16 BLS Macro Release-Day Drift Update

Added `es_bls_macro_release_day_drift`. All five original variants failed
`limited_core_grid_test` and all five one-time parameter-space/fixed-parameter
rescues were run. Every original and rescue failed `limited_core_grid_test`; no
run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen
validation.

Verified active sweep after this update: 160 active source variants, 160 rescue
configs, 338 raw variant-level reports, 0 passes, 0 active variants missing a
latest original report, and 0 active variants missing `rescue1`.

## 2026-06-16 Term-Structure Lead-Lag Feedback Update

Added `es_term_structure_lead_lag_feedback`. All five original variants failed
`limited_core_grid_test` and all five one-time parameter-space rescues were run.
Every original and rescue failed `limited_core_grid_test`; no run reached
monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

Verified active sweep after this update: 165 active source variants, 165 rescue
configs, 348 raw variant-level reports, 0 passes, 0 active variants missing any
original run, and 0 active variants missing `rescue1`.

## 2026-06-16 Monthly OPEX Pressure Update

Added `es_monthly_opex_pressure`. All five original variants failed
`limited_core_grid_test` and all five one-time stop/target parameter-space
rescues were run. Every original and rescue failed `limited_core_grid_test`; no
run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen
validation.

Verified active sweep after this update: 170 active source variants, 170 rescue
configs, 358 raw variant-level reports, 0 passes, 0 active variants missing any
original run, and 0 active variants missing `rescue1`.

## 2026-06-16 VIX Expiration Pressure Update

Added `es_vix_expiration_pressure`. All five original variants failed
`limited_core_grid_test` and all five one-time stop/target parameter-space
rescues were run. Every original and rescue failed `limited_core_grid_test`; no
run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen
validation.

Verified active sweep after this update: 175 active source variants, 175 rescue
configs, 368 raw variant-level reports, 0 passes, 0 active variants missing any
original run, and 0 active variants missing `rescue1`.
