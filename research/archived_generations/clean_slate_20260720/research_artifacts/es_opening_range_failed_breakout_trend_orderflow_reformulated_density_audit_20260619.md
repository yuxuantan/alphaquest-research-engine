# ES Trend-Filtered OR Failed Breakout Reformulated Density Audit

Purpose: pre-PnL signal-density check for the reformulated active source set before staged backtests.

Full-history subset: 2011-01-03 to 2026-06-09
Limited-core resolved random 10% subset: 2011-02-22 to 2012-09-06

This audit uses a conservative implementation-aligned day loop for the completed opening-range outside-close, frozen pre-breakout trend context, reclaim, and completed orderflow confirmation. It intentionally does not compute PnL, stops, targets, or fills.

| variant_id | full_min_signals_per_year | limited_min_signals_per_year | passed_density_floor |
| --- | ---: | ---: | --- |
| or15_full_session_large10_trend_reclaim_1530 | 97.45 | 86.28 | True |
| or15_full_session_signed_trend_reclaim_1530 | 101.73 | 85.64 | True |
| or30_full_session_large10_trend_reclaim_1530 | 88.12 | 77.85 | True |
| or30_full_session_signed_trend_reclaim_1530 | 92.53 | 78.50 | True |
| or60_full_session_signed_trend_reclaim_1530 | 77.30 | 61.63 | True |

Detailed CSV: `research_artifacts/es_opening_range_failed_breakout_trend_orderflow_reformulated_density_audit_20260619.csv`
