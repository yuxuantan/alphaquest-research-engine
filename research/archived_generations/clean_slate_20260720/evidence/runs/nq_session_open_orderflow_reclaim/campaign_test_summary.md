# nq_session_open_orderflow_reclaim campaign test summary

Decision: FAIL

Rejected before staged NQ PnL: 9/45 declared session-open reclaim entry-grid rows failed the pre-PnL density gate. Sparse rows appeared in three variants, with the weakest limited-core proxy density at 39.50 signals/year. Dropping the sparse direction/time-window corners after this screen would change the declared five-variant edge after observing signal availability. No NQ PnL was inspected.

No staged PnL, monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run because the pre-PnL density gate failed.

| variant_id | entry_rows | rows_passing | min_full_per_year | min_limited_per_year | min_latest252 | pass |
|---|---:|---:|---:|---:|---:|---|
| `afternoon_large20_down_open_reclaim_long` | 9 | 9 | 102.78 | 60.23 | 133 | PASS |
| `afternoon_large20_up_open_reject_short` | 9 | 6 | 86.78 | 45.98 | 112 | FAIL |
| `midday_large10_two_sided_open_reclaim` | 9 | 9 | 161.19 | 96.49 | 214 | PASS |
| `morning_down_open_reclaim_long` | 9 | 6 | 116.57 | 44.68 | 175 | FAIL |
| `morning_up_open_reject_short` | 9 | 6 | 110.42 | 39.50 | 171 | FAIL |

Density audit: `research_artifacts/nq_session_open_orderflow_reclaim_density_audit_20260630.md`
