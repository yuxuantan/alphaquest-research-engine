# ES Opening Gap Orderflow Absorption Fade Rescue Attempt 1

Date: 2026-06-17

Reason for rescue:
- All five original variants failed `limited_core_grid_test`.
- Original profitable-combination rate was 0.0 for every variant.
- No original variant reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

Rescue scope:
- One rescue is applied to each failed variant, consistent with the per-failed-variant rescue rule.
- The rescue is parameter-space-only.

Unchanged:
- Entry module: `opening_gap_orderflow_fade`
- Stop module: `percent_from_entry`
- Target module: `fixed_r`
- Entry source windows
- Direction mode
- Flow bucket
- Opening-gap plus aggregate-flow-absorption mechanic
- Dataset and date window
- Costs, slippage, tick size, point value
- Session, flatten, prop-rule, and fill assumptions
- Stage criteria

Changed:
- Fixed stop default: `sl.params.stop_pct` from `0.0015` to `0.004`
- Fixed target default: `tp.params.target_r_multiple` from `0.75` to `1.5`
- Stop grid from `[0.001, 0.0015, 0.0025]` to `[0.0025, 0.004, 0.006]`
- Target grid from `[0.5, 0.75, 1.0]` to `[1.0, 1.5, 2.0]`

Rationale:
- The original least-bad rows were still net negative, but several variants used the widest original stop and target in their best rows. The rescue tests whether the original exits were too tight for gap-absorption trades.
- This is not a mechanics change. It does not alter signal timing, gap threshold grid, orderflow threshold grid, side selection, source window, or data.

Configs:
- `campaigns/es_opening_gap_orderflow_absorption_fade/rescue_attempts/parameter_space_rescue_1/early_large20_gap_absorption_fade_1000/config.yaml`
- `campaigns/es_opening_gap_orderflow_absorption_fade/rescue_attempts/parameter_space_rescue_1/morning_large20_gap_absorption_fade_1030/config.yaml`
- `campaigns/es_opening_gap_orderflow_absorption_fade/rescue_attempts/parameter_space_rescue_1/late_morning_large20_gap_absorption_fade_1100/config.yaml`
- `campaigns/es_opening_gap_orderflow_absorption_fade/rescue_attempts/parameter_space_rescue_1/midday_large20_gap_absorption_fade_1200/config.yaml`
- `campaigns/es_opening_gap_orderflow_absorption_fade/rescue_attempts/parameter_space_rescue_1/late_morning_large10_gap_absorption_fade_1100/config.yaml`
