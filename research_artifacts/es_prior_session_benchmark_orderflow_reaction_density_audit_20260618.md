# ES Prior Session Benchmark Orderflow Reaction Density Audit

Generated: 2026-06-18

Purpose: pre-PnL trade-frequency check before staged profit testing. This audit counts completed-bar entry signals only; it does not inspect net profit, drawdown, profit factor, expectancy, or any result metric.

## Data Windows

- Full configured subset: `{'start_date': '2011-01-03', 'end_date': '2026-06-09', 'session_labels': ['RTH']}`
- Full span years: `15.433265`
- Limited-core resolved subset: `{'start_date': '2011-02-22', 'end_date': '2012-09-06', 'session_labels': ['RTH']}`
- Limited-core span years: `1.541410`
- Limited-core selection rule: runner-default random 10% period, seed `31`, avoiding the latest 10% of available data and avoiding `2020-02-01` through `2021-06-30`.

## Density Summary

| variant_id | best_full_tpy | best_full_probe | best_full_imbalance | best_limited_tpy | best_limited_probe | best_limited_imbalance | density_gate_pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| prior_close_midday_large10_reclaim_reversion_1400 | 89.417243 | 0 | 0.0 | 76.553286 | 0 | 0.0 | true |
| prior_close_morning_signed_reclaim_reversion_1130 | 112.484300 | 0 | 0.0 | 107.693606 | 0 | 0.0 | true |
| prior_open_close_afternoon_signed_reclaim_reversion_1530 | 102.376264 | 0 | 0.0 | 97.313499 | 0 | 0.0 | true |
| prior_open_midday_large20_reclaim_reversion_1400 | 58.833954 | 0 | 0.0 | 54.495560 | 0 | 0.0 | true |
| prior_open_morning_signed_reclaim_reversion_1130 | 70.432278 | 0 | 0.0 | 57.090586 | 0 | 0.0 | true |

## Decision

All five variants have at least one predeclared entry-grid point capable of reaching 50 signals/year on both full data and the limited-core shortlist window. Proceed to preflight and staged testing without changing mechanics after this point.

Some strict corners are borderline in the limited-core window, especially `prior_open_morning_signed_reclaim_reversion_1130` with `min_probe_ticks = 2`, which produced `49.954263` signals/year in the shortlist sample. This is documented as a parameter-space density caveat, not a post-result change trigger.

## Artifact Paths

- Detailed grid: `research_artifacts/es_prior_session_benchmark_orderflow_reaction_density_audit_20260618.csv`
- Summary CSV: `research_artifacts/es_prior_session_benchmark_orderflow_reaction_density_summary_20260618.csv`
