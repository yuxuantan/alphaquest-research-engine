# NQ Semivariance Orderflow Confirmation Density Audit - 2026-06-22

Purpose: count raw entry signals before any PnL inspection so sparse parameter spaces are rejected before staged testing rather than interpreted as expectancy evidence.

Method:
- Uses authored configs under `campaigns/nq_semivariance_orderflow_confirmation/variants/*/config.yaml`.
- Expands the declared `core_grid.parameters` exactly as authored using the same dotted-parameter semantics as `run_core_grid`.
- Prepares the same 5-minute RTH NQ orderflow feature bars as the staged runner with `prepare_data`.
- Applies the entry-module conditions vectorially: lagged semivariance rank/value, current RTH-open move, completed rolling orderflow imbalance, fixed decision times, and one signal per day.
- Does not inspect fills, stops, targets, trade PnL, equity curves, or future data.

Limited-core window: `2011-02-22` to `2012-09-07`. Full core-history window: `2011-01-03` to `2026-06-12`.

Density guideline: every variant should have at least 50 limited-core signals/year before staged testing.

| variant | window | combos | min signals | median signals | max signals | min signals/year | median signals/year | max signals/year | density pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| badvol_signed_multitime_short | limited_core_window | 36 | 93 | 98 | 104 | 60.23 | 63.79 | 67.35 | true |
| badvol_signed_multitime_short | full_available_history | 36 | 863 | 978 | 1106 | 55.89 | 63.37 | 71.63 | true |
| badvol_signed_multitime_twosided | limited_core_window | 36 | 174 | 194 | 216 | 112.68 | 125.31 | 139.88 | true |
| badvol_signed_multitime_twosided | full_available_history | 36 | 1420 | 1931 | 2319 | 91.96 | 125.05 | 150.18 | true |
| downside_share_signed_multitime_short | limited_core_window | 36 | 86 | 96 | 109 | 55.69 | 62.49 | 70.59 | true |
| downside_share_signed_multitime_short | full_available_history | 36 | 689 | 936 | 1125 | 44.62 | 60.58 | 72.86 | false |
| low_badvol_signed_multitime_long | limited_core_window | 36 | 88 | 99 | 113 | 56.99 | 64.11 | 73.18 | true |
| low_badvol_signed_multitime_long | full_available_history | 36 | 774 | 1024 | 1225 | 50.12 | 66.28 | 79.33 | true |
| semivar_balance_signed_multitime_twosided | limited_core_window | 36 | 144 | 171 | 204 | 93.26 | 110.74 | 132.11 | true |
| semivar_balance_signed_multitime_twosided | full_available_history | 36 | 1070 | 1604 | 2038 | 69.29 | 103.88 | 131.98 | true |

CSV: `research_artifacts/nq_semivariance_orderflow_confirmation_density_audit_20260622.csv`
