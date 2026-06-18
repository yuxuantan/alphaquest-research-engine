# ES Semivariance Orderflow Confirmation Reformulated Density Audit - 2026-06-18

Purpose: verify the final pre-test multi-time variants have enough raw signal density before staged PnL testing.

Method:
- Uses the final authored configs under `campaigns/es_semivariance_orderflow_confirmation/variants/*/config.yaml`.
- Expands the declared core-grid parameter space exactly as authored using the same dotted-parameter semantics as `run_core_grid`.
- Feeds each session RTH open bar plus all configured completed signal bars into the entry module in chronological order.
- Counts entry-module signals only; no fills, stops, targets, trade PnL, equity curves, or future data are inspected.

Limited-core window: `2011-02-22` to `2012-09-06`. Full core-history window: `2011-01-03` to `2026-06-09`.

| variant | window | combos | min signals | median signals | max signals | min signals/year | median signals/year | max signals/year | density pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| badvol_signed_multitime_short | limited_core_window | 54 | 94 | 106 | 113 | 63.34 | 71.42 | 76.14 | true |
| badvol_signed_multitime_short | full_available_history | 54 | 856 | 973 | 1077 | 56.51 | 64.24 | 71.10 | true |
| badvol_signed_multitime_twosided | limited_core_window | 54 | 178 | 199 | 219 | 119.94 | 134.09 | 147.56 | true |
| badvol_signed_multitime_twosided | full_available_history | 54 | 1568 | 2104 | 2346 | 103.52 | 138.91 | 154.88 | true |
| downside_share_signed_multitime_short | limited_core_window | 54 | 100 | 111 | 120 | 67.38 | 74.79 | 80.86 | true |
| downside_share_signed_multitime_short | full_available_history | 54 | 791 | 1052 | 1169 | 52.22 | 69.45 | 77.18 | true |
| low_badvol_signed_multitime_long | limited_core_window | 54 | 88 | 99 | 108 | 59.29 | 66.71 | 72.77 | true |
| low_badvol_signed_multitime_long | full_available_history | 54 | 892 | 1163 | 1282 | 58.89 | 76.78 | 84.64 | true |
| semivar_balance_signed_multitime_twosided | limited_core_window | 54 | 154 | 185 | 202 | 103.76 | 124.65 | 136.11 | true |
| semivar_balance_signed_multitime_twosided | full_available_history | 54 | 1299 | 1799 | 2090 | 85.76 | 118.77 | 137.98 | true |

CSV: `research_artifacts/es_semivariance_orderflow_confirmation_reformulated_density_audit_20260618.csv`
