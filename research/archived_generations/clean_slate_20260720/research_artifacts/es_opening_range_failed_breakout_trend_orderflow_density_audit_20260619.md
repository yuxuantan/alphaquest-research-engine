# ES Trend-Filtered OR Failed Breakout Density Audit

Purpose: pre-PnL signal-density check before staged backtests.

Full-history subset: 2011-01-03 to 2026-06-09
Limited-core resolved random 10% subset: 2011-02-22 to 2012-09-06

Entry grid counted only signal-affecting parameters: `min_trend_move_ticks` x `min_reclaim_orderflow_imbalance`. Stop and target grids do not affect signal frequency.

## Summary

| variant_id | full_min_signals_per_year | limited_min_signals_per_year | passed_density_floor |
| --- | --- | --- | --- |
| or15_downtrend_upside_reject_short_1030 | 8.68 | 2.60 | False |
| or15_uptrend_downside_reclaim_long_1030 | 10.43 | 6.49 | False |
| or30_large10_two_sided_trend_reclaim_1130 | 26.31 | 18.17 | False |
| or30_signed_two_sided_trend_reclaim_1100 | 17.30 | 12.33 | False |
| or60_signed_two_sided_trend_reclaim_1230 | 24.30 | 18.17 | False |

Detailed CSV: `research_artifacts/es_opening_range_failed_breakout_trend_orderflow_density_audit_20260619.csv`
