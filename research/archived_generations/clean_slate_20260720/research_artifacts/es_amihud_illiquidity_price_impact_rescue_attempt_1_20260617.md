# ES Amihud Illiquidity Price Impact Rescue Attempt 1

Date: 2026-06-17

Scope: one parameter-space rescue for every failed original variant.

Allowed changes used:
- `entry.params.illiq_rank_threshold`: `[0.20, 0.30, 0.40]`
- `sl.params.stop_pct`: `[0.001, 0.002, 0.0035]`
- `tp.params.target_r_multiple`: `[1.5, 2.5, 3.5]`

Forbidden changes not made: entry module, direction mode, feature CSV, rank/value columns, timeframe, data window, costs, fill assumptions, stage criteria, stop module, target module, and edge thesis.

Configs:
- `high_1d_illiq_premium_long_1000`: `campaigns/es_amihud_illiquidity_price_impact/rescue_attempts/parameter_space_rescue_1/high_1d_illiq_premium_long_1000/config.yaml`
- `high_1d_illiq_stress_short_1030`: `campaigns/es_amihud_illiquidity_price_impact/rescue_attempts/parameter_space_rescue_1/high_1d_illiq_stress_short_1030/config.yaml`
- `high_20d_illiq_premium_long_1200`: `campaigns/es_amihud_illiquidity_price_impact/rescue_attempts/parameter_space_rescue_1/high_20d_illiq_premium_long_1200/config.yaml`
- `high_5d_illiq_premium_long_1130`: `campaigns/es_amihud_illiquidity_price_impact/rescue_attempts/parameter_space_rescue_1/high_5d_illiq_premium_long_1130/config.yaml`
- `two_sided_5d_illiq_state_1330`: `campaigns/es_amihud_illiquidity_price_impact/rescue_attempts/parameter_space_rescue_1/two_sided_5d_illiq_state_1330/config.yaml`
