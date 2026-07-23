# ES Semivariance Orderflow Confirmation Density Audit - 2026-06-18

Purpose: count raw entry signals before any PnL inspection so sparse parameter spaces are rejected or rescued as representation failures rather than interpreted as weak expectancy.

Method:
- Uses the authored configs under `campaigns/es_semivariance_orderflow_confirmation/variants/*/config.yaml`.
- Expands the declared core-grid parameter space exactly as authored using the same dotted-parameter semantics as `run_core_grid`.
- Feeds each session RTH open bar plus the configured completed signal bar into the entry module, preserving session-open state.
- Counts entry-module signals only; no fills, stops, targets, trade PnL, equity curves, or future data are inspected.
- Reports both the canonical limited-core shortlist window and full available core-history window.

Limited-core window: `2011-02-22` to `2012-09-06`. Full core-history window: `2011-01-03` to `2026-06-09`.

Density guideline: each original variant intended for staged testing should have at least 50 limited-core signals/year for a meaningful chance to satisfy the later WFA trade-count gate.

| variant | window | combos | min signals | median signals | max signals | min signals/year | median signals/year | max signals/year | density pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| badvol_60m_confirmed_short_1030 | limited_core_window | 81 | 14 | 34 | 49 | 9.43 | 22.91 | 33.02 | false |
| badvol_60m_confirmed_short_1030 | full_available_history | 81 | 35 | 174 | 387 | 2.31 | 11.49 | 25.55 | false |
| badvol_90m_confirmed_short_1100 | limited_core_window | 81 | 8 | 34 | 49 | 5.39 | 22.91 | 33.02 | false |
| badvol_90m_confirmed_short_1100 | full_available_history | 81 | 24 | 159 | 382 | 1.58 | 10.50 | 25.22 | false |
| badvol_large10_confirmed_short_1030 | limited_core_window | 81 | 2 | 22 | 45 | 1.35 | 14.82 | 30.32 | false |
| badvol_large10_confirmed_short_1030 | full_available_history | 81 | 77 | 181 | 331 | 5.08 | 11.95 | 21.85 | false |
| downside_share_60m_confirmed_short_1130 | limited_core_window | 81 | 11 | 28 | 39 | 7.41 | 18.87 | 26.28 | false |
| downside_share_60m_confirmed_short_1130 | full_available_history | 81 | 53 | 188 | 333 | 3.50 | 12.41 | 21.98 | false |
| low_badvol_60m_confirmed_long_1030 | limited_core_window | 81 | 15 | 28 | 38 | 10.11 | 18.87 | 25.60 | false |
| low_badvol_60m_confirmed_long_1030 | full_available_history | 81 | 58 | 232 | 460 | 3.83 | 15.32 | 30.37 | false |

CSV: `research_artifacts/es_semivariance_orderflow_confirmation_density_audit_20260618.csv`
