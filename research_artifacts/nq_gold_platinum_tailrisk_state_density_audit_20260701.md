# nq_gold_platinum_tailrisk_state Density Audit

Decision: FAIL

Gate: every declared entry row must have at least 5 full-history signals/year, 5 early-window signals/year, and 5 signals in the latest 252 sessions.

| variant | pass_rows | rows | min_full_per_year | min_limited_per_year | min_latest_252 | verdict |
|---|---:|---:|---:|---:|---:|---|
| gp_falling_morning_strength_long_1130 | 9 | 9 | 29.73 | 28.20 | 35 | PASS |
| gp_rising_morning_weakness_short_1130 | 9 | 9 | 28.49 | 24.84 | 28 | PASS |
| high_gp_risk_premium_long_1000 | 3 | 9 | 126.87 | 157.78 | 0 | FAIL |
| high_gp_risk_premium_long_1430 | 3 | 9 | 126.87 | 157.78 | 0 | FAIL |
| low_gp_complacency_short_1000 | 6 | 9 | 47.92 | 0.00 | 177 | FAIL |

Detail CSV: `research_artifacts/nq_gold_platinum_tailrisk_state_density_audit_20260701.csv`
Summary CSV: `research_artifacts/nq_gold_platinum_tailrisk_state_density_summary_20260701.csv`
