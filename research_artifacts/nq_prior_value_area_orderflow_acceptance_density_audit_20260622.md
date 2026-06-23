# NQ Prior Value-Area Orderflow Acceptance Density Audit - 2026-06-22

Purpose: count raw entry signals before any PnL inspection so sparse parameter spaces are rejected before staged testing rather than interpreted as expectancy evidence.

Method:
- Uses authored configs under `campaigns/nq_prior_value_area_orderflow_acceptance/variants/*/config.yaml`.
- Expands declared `core_grid.parameters` exactly as authored.
- Prepares the same 5-minute NQ RTH orderflow bars as the staged runner with `prepare_data`.
- Builds approximate prior-session VAH/VAL/POC from completed bars only, then applies acceptance and orderflow conditions vectorially.
- Does not inspect fills, stops, targets, trade PnL, equity curves, or future data.

Limited-core window: `2011-02-22` to `2012-09-07`. Full core-history window: `2011-01-03` to `2026-06-12`.

Density guideline: every variant should have at least 50 limited-core signals/year before staged testing.

| variant | window | combos | min signals | median signals | max signals | min signals/year | median signals/year | max signals/year | density pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| afternoon_large20_two_sided_acceptance | limited_core_window | 81 | 320 | 324 | 326 | 207.23 | 209.82 | 211.12 | true |
| afternoon_large20_two_sided_acceptance | full_available_history | 81 | 3295 | 3303 | 3319 | 213.39 | 213.90 | 214.94 | true |
| late_morning_large10_two_sided_acceptance | limited_core_window | 54 | 331 | 336 | 338 | 214.36 | 217.60 | 218.89 | true |
| late_morning_large10_two_sided_acceptance | full_available_history | 54 | 3512 | 3522 | 3532 | 227.44 | 228.09 | 228.73 | true |
| midday_signed_two_sided_acceptance | limited_core_window | 27 | 330 | 333 | 336 | 213.71 | 215.65 | 217.60 | true |
| midday_signed_two_sided_acceptance | full_available_history | 27 | 3444 | 3462 | 3478 | 223.04 | 224.20 | 225.24 | true |
| morning_signed_vah_acceptance_long | limited_core_window | 54 | 192 | 194 | 196 | 124.34 | 125.64 | 126.93 | true |
| morning_signed_vah_acceptance_long | full_available_history | 54 | 2136 | 2185 | 2215 | 138.33 | 141.50 | 143.44 | true |
| morning_signed_val_acceptance_short | limited_core_window | 54 | 165 | 169 | 171 | 106.86 | 109.45 | 110.74 | true |
| morning_signed_val_acceptance_short | full_available_history | 54 | 1646 | 1667 | 1684 | 106.60 | 107.96 | 109.06 | true |

CSV: `research_artifacts/nq_prior_value_area_orderflow_acceptance_density_audit_20260622.csv`
