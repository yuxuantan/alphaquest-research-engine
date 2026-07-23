# nq_key_reversal_orderflow_reversal campaign test summary

Decision: FAIL

Rejected before staged NQ PnL: 14/30 declared prior-bar key-reversal entry-grid rows failed the pre-PnL density gate. All five variants had at least one sparse limited-core proxy row; the weakest limited-core proxy density was 18.78 signals/year. Dropping sparse variants, time windows, or grid corners after this screen would change the declared five-variant edge after observing signal availability. No NQ PnL was inspected.

No staged PnL, monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run because the pre-PnL density gate failed.

| variant_id | entry_rows | rows_passing | min_full_per_year | min_limited_per_year | min_latest252 | pass |
|---|---:|---:|---:|---:|---:|---|
| `afternoon_large20_two_sided_key_reversal_1530` | 6 | 3 | 93.32 | 22.02 | 163 | FAIL |
| `late_morning_large10_down_sweep_reclaim_long_1230` | 6 | 3 | 141.96 | 37.56 | 236 | FAIL |
| `late_morning_large10_up_sweep_reject_short_1230` | 6 | 3 | 139.49 | 40.15 | 235 | FAIL |
| `midday_signed_two_sided_key_reversal_1400` | 6 | 3 | 134.96 | 18.78 | 248 | FAIL |
| `morning_signed_two_sided_key_reversal_1130` | 6 | 4 | 164.88 | 47.92 | 252 | FAIL |

Density audit: `research_artifacts/nq_key_reversal_orderflow_reversal_density_audit_20260630.md`
