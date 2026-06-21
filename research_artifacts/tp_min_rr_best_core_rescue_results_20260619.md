# TP Minimum-RR Best-Core Rescue Batch - 2026-06-19

- Batch id: `tp_min_rr_floor_rescue_1_user_authorized_20260619`
- Runs summarized: 94
- Campaigns skipped by minimum-RR rule: 25
- Full-stage passes: 0
- Fixed-config core trade logs found in result paths: 94

## Terminal Stage Counts

- `limited_core_grid_test`: 90
- `walk_forward_analysis`: 3
- `limited_monkey_test`: 1

## Strongest Partial Results

| campaign | variant | terminal | core profitable | core passing | WFA PF | WFA MAR | WFA trades/yr | MC pass chance |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| es_prior_value_area_orderflow_acceptance | morning_signed_vah_acceptance_long | walk_forward_analysis | 0.7777777777777778 | 33/54 | 1.0097187453983214 | 0.05524115840597269 | 84.06830143074343 |  |
| es_semivariance_orderflow_confirmation | badvol_signed_multitime_twosided | walk_forward_analysis | 0.7222222222222222 | 10/18 | 0.5956962025316456 | -0.9333625893824896 | 119.29420659306574 |  |
| es_vpin_toxicity_continuation | slow_bucket_toxicity_long_1330 | walk_forward_analysis | 0.9629629629629629 | 0/54 | 0.0 | 0.0 | 0.0 |  |
| es_usdjpy_safe_haven_spillover | weak_yen_long_1200 | limited_monkey_test | 1.0 | 0/18 |  |  |  |  |
| es_orderflow_absorption_exhaustion_reversal | early_5m_absorption_fade_1000 | limited_core_grid_test | 0.6666666666666666 | 0/54 |  |  |  |  |
| es_epu_policy_uncertainty_intraday | low_epu_long_1030 | limited_core_grid_test | 0.5555555555555556 | 6/18 |  |  |  |  |
| es_opening_drive_mes_crowding_reversal | od30_notional_failed_extension_reversal_1300 | limited_core_grid_test | 0.5555555555555556 | 3/27 |  |  |  |  |
| es_realized_semivariance_asymmetry | high_goodvol_fade_short_1200 | limited_core_grid_test | 0.4444444444444444 | 5/18 |  |  |  |  |
| es_monthly_opex_pressure | nonquarterly_post_opex_monday_reversal_long_1000 | limited_core_grid_test | 0.4166666666666667 | 0/12 |  |  |  |  |
| es_prior_session_breakout_orderflow_confirmation | first_half_signed_no_buffer_break_two_sided | limited_core_grid_test | 0.3333333333333333 | 4/24 |  |  |  |  |

## Decision

FAIL. This user-authorized minimum-RR rescue produced no full staged pass and no new candidate strategy report.

- CSV: `research_artifacts/tp_min_rr_best_core_rescue_results_20260619.csv`
- JSON: `research_artifacts/tp_min_rr_best_core_rescue_results_20260619.json`
