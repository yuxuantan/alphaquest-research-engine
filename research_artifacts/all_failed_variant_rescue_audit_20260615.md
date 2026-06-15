# All Failed Variant Rescue Audit

Date: 2026-06-15

Decision: FAIL

## Scope

The user clarified that each failed variant can receive one rescue run. This audit records the resulting per-variant rescue coverage across the active ES campaigns. A rescue may change only existing fixed parameters or tunable parameter space inside existing modules; it may not change the core strategy mechanic, modules, timeframe, data window, costs, fill assumptions, or validation gates.

## Coverage

- Active variant configs checked: 35
- Rescue configs present: 35
- Active variants missing `rescue1` report: 0
- Rescue reports with `passed=true`: 0
- Final decision from rescue coverage: FAIL

## Verification Commands

```bash
python3 -m research.preflight --skip-tests
for cfg in campaigns/*/rescue_attempts/parameter_space_rescue_1/*/config.yaml; do python3 -m research.preflight --config "$cfg" --skip-tests; done
python3 -m propstack.run_campaign_stages --config <missing_rescue_config.yaml> --fast-runtime-defaults
```

Preflight results: repo-wide preflight passed with 108 active configs after the
signed-orderflow campaign was added; targeted preflight passed for the five new
signed-orderflow rescue configs and the staged rescue run completed. The
earlier staged loop ran the 23 previously missing `rescue1` reports and skipped
no existing reports. Existing `rescue1` reports were retained and not rerun.

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

## Conclusion

Every active failed ES variant now has exactly one `rescue1` report. All rescues failed before WFA or at the limited monkey gate. No rescue produced a candidate strategy for manual chart review or paper incubation. No second rescue is permitted for any of these variants under the current rule.

The search remains fail-closed for the active campaign set. Archived tests are
ignored for duplicate-edge checks; see
`research_artifacts/duplicate_edge_scope_policy_20260615.md`. Further progress
requires either a new edge that is not already active and has available local
data, or explicit approval for the retained external-data branches documented
in `research_artifacts/local_no_duplicate_data_gate_audit_20260615.md`.
