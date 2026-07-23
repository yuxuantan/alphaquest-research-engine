# ES Prior Session Benchmark Orderflow Reaction Rescue 1 Density Audit

Generated: 2026-06-18T18:09:24

Purpose: pre-PnL signal-density check for the parameter-space rescue. This does not inspect profit or drawdown.

## Data Windows

- Full configured subset: `{'start_date': '2011-01-03', 'end_date': '2026-06-09', 'session_labels': ['RTH']}`
- Full actual first timestamp: `2011-01-03 09:30:00-05:00`
- Full actual last timestamp: `2026-06-09 15:59:00-04:00`
- Full span years: `15.433265`
- Limited-core resolved subset: `{'start_date': '2011-02-22', 'end_date': '2012-09-06', 'session_labels': ['RTH']}`
- Limited-core actual first timestamp: `2011-02-22 09:30:00-05:00`
- Limited-core actual last timestamp: `2012-09-06 15:59:00-04:00`
- Limited-core span years: `1.541410`

## Density Summary

| variant_id | best_full_tpy | best_full_probe | best_full_imbalance | best_limited_tpy | best_limited_probe | best_limited_imbalance | density_gate_pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| prior_close_midday_large10_reclaim_reversion_1400 | 84.233635 | 1 | 0.02 | 74.607016 | 1 | 0.02 | true |
| prior_close_morning_signed_reclaim_reversion_1130 | 106.652741 | 1 | 0.02 | 102.503552 | 1 | 0.02 | true |
| prior_open_close_afternoon_signed_reclaim_reversion_1530 | 96.933475 | 1 | 0.02 | 88.230906 | 1 | 0.02 | true |
| prior_open_midday_large20_reclaim_reversion_1400 | 56.566126 | 1 | 0.02 | 51.900533 | 1 | 0.02 | true |
| prior_open_morning_signed_reclaim_reversion_1130 | 66.350186 | 1 | 0.02 | 55.793073 | 1 | 0.02 | true |

## Decision

All five rescue variants have at least one predeclared entry-grid point capable of reaching 50 signals/year on both full data and the limited-core shortlist window. Proceed to staged rescue testing without changing mechanics.

- Detailed grid: `research_artifacts/es_prior_session_benchmark_orderflow_reaction_rescue_attempt_1_density_audit_20260618.csv`
- Summary CSV: `research_artifacts/es_prior_session_benchmark_orderflow_reaction_rescue_attempt_1_density_summary_20260618.csv`
