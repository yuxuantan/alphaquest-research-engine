# nq_move_treasury_volatility_state Density Audit

Decision: FAIL

Gate: every declared entry row must have at least 5 full-history signals/year, 5 early-window signals/year, and 5 signals in the latest 252 sessions.

| variant | pass_rows | rows | min_full_per_year | min_limited_per_year | min_latest_252 | verdict |
|---|---:|---:|---:|---:|---:|---|
| high_move_riskoff_short_1000 | 8 | 9 | 20.66 | 12.09 | 4 | FAIL |
| high_move_riskoff_short_1430 | 8 | 9 | 20.66 | 12.09 | 4 | FAIL |
| low_move_carry_long_1000 | 9 | 9 | 18.46 | 24.17 | 32 | PASS |
| move_crush_morning_strength_long_1130 | 9 | 9 | 29.08 | 22.83 | 33 | PASS |
| move_spike_morning_weakness_short_1130 | 9 | 9 | 25.52 | 18.80 | 26 | PASS |

Detail CSV: `research_artifacts/nq_move_treasury_volatility_state_density_audit_20260701.csv`
Summary CSV: `research_artifacts/nq_move_treasury_volatility_state_density_summary_20260701.csv`
