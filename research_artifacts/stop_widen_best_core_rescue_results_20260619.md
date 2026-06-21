# Stop-Widen Best-Core Rescue Batch - 2026-06-19

- Batch id: `stop_distance_rescue_1_user_authorized_20260619`
- Runs summarized: 118
- Full-stage passes: 0
- Fixed-config core trade logs found in result paths: 118

## Terminal Stage Counts

- `limited_core_grid_test`: 91
- `walk_forward_analysis`: 14
- `limited_monkey_test`: 12
- `wfa_oos_monte_carlo`: 1

## Strongest Partial Results

| campaign | variant | terminal | core profitable | core passing | WFA PF | WFA MAR | WFA trades/yr | MC pass chance |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| es_trend_filtered_mes_participation_crowding | morning_trade_trend_pullback_reversal_1030 | wfa_oos_monte_carlo | 1.0 | 79/81 | 1.4479787172517495 | 2.4985322265215255 | 77.38112507379607 | 0.0 |
| es_prior_value_area_orderflow_acceptance | morning_signed_vah_acceptance_long | walk_forward_analysis | 0.7407407407407407 | 35/81 | 0.8712250271023695 | -0.6220104681635704 | 84.06830143074343 |  |
| es_mes_participation_crowding_reversion | morning_notional_down_reversal_long_1030 | walk_forward_analysis | 1.0 | 54/81 | 0.8355944208346955 | -0.32222560243240006 | 56.59904169640126 |  |
| es_cboe_implied_correlation_intraday | high_short_term_correlation_short_1330 | walk_forward_analysis | 1.0 | 19/27 | 0.8000746454341876 | -0.5411166119369513 | 108.15061534859575 |  |
| es_ofr_financial_stress_intraday | high_credit_stress_short_1030 | walk_forward_analysis | 0.8148148148148148 | 5/27 | 0.7759546411236631 | -0.7833620062993929 | 210.90111330666537 |  |
| es_nq_relative_value_orderflow_absorption_reversion | midday60_two_sided_absorption_1400 | walk_forward_analysis | 0.8271604938271605 | 10/81 | 0.7169466764061359 | -0.6975521321854036 | 40.80309072008192 |  |
| es_vpin_toxicity_continuation | slow_bucket_toxicity_long_1330 | walk_forward_analysis | 1.0 | 0/81 | 0.0 | 0.0 | 0.0 |  |
| es_quarterly_expiration_pressure | monday_after_expiration_reversal_long_1000 | limited_monkey_test | 1.0 | 0/12 |  |  |  |  |
| es_prior_session_level_breakout_continuation | morning_prior_high_breakout_long | limited_monkey_test | 1.0 | 0/81 |  |  |  |  |
| es_range_compression_breakout | id_nr4_prior_session_breakout | limited_monkey_test | 1.0 | 0/81 |  |  |  |  |

## Post-WFA Failure

- `es_trend_filtered_mes_participation_crowding/morning_trade_trend_pullback_reversal_1030` reached post-WFA and failed at `wfa_oos_monte_carlo`. WFA PF `1.4479787172517495`, WFA MAR `2.4985322265215255`, trades/year `77.38112507379607`, Monte Carlo profit-before-drawdown probability `0.0`.

## Decision

FAIL. This user-authorized stop-distance rescue produced no full staged pass and no new candidate strategy report.

- CSV: `research_artifacts/stop_widen_best_core_rescue_results_20260619.csv`
- JSON: `research_artifacts/stop_widen_best_core_rescue_results_20260619.json`
