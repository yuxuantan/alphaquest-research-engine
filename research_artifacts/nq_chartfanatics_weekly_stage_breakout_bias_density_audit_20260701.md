# nq_chartfanatics_weekly_stage_breakout_bias Density Audit

Decision: PASS

Gate: every declared entry row must have at least 5 full-history signals/year, 5 early-window signals/year, and 5 signals in the latest 252 sessions.

| variant | pass_rows | rows | min_full_per_year | min_limited_per_year | min_latest_252 | verdict |
|---|---:|---:|---:|---:|---:|---|
| stage2_compression_breakout_1200 | 9 | 9 | 27.20 | 12.76 | 32 | PASS |
| stage2_opening_or_breakout_1030 | 9 | 9 | 77.65 | 34.91 | 108 | PASS |
| stage2_prior_close_reclaim_1200 | 9 | 9 | 70.01 | 29.54 | 78 | PASS |
| stage2_prior_high_reclaim_1130 | 9 | 9 | 74.73 | 32.23 | 102 | PASS |
| stage2_weekly_support_reclaim_1430 | 9 | 9 | 46.30 | 14.10 | 50 | PASS |

Detail CSV: `research_artifacts/nq_chartfanatics_weekly_stage_breakout_bias_density_audit_20260701.csv`
Summary CSV: `research_artifacts/nq_chartfanatics_weekly_stage_breakout_bias_density_summary_20260701.csv`
