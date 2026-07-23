# nq_prior_session_benchmark_orderflow_reaction density audit

- Audit date: 2026-06-30
- Source campaign: es_prior_session_benchmark_orderflow_reaction
- Full window: 2011-01-03 to 2026-06-12 (3813 sessions)
- Limited-core window: 2011-02-22 to 2012-09-07
- Latest-252 window: 2025-06-09 to 2026-06-12
- Declared entry rows: 45
- Density passes: 36
- Density failures: 9

Gate: every declared entry row must produce at least 50 signals/year in full history, at least 50 signals/year in the limited-core window, and at least 50 signals in the latest 252 sessions before any PnL is inspected.

| variant | rows | pass rows | min full/year | min limited/year | min latest-252 | verdict |
|---|---:|---:|---:|---:|---:|---|
| prior_close_midday_large10_reclaim_reversion_1400 | 9 | 9 | 79.22 | 70.71 | 72 | PASS |
| prior_close_morning_signed_reclaim_reversion_1130 | 9 | 9 | 108.69 | 103.80 | 89 | PASS |
| prior_open_close_afternoon_signed_reclaim_reversion_1530 | 9 | 9 | 92.49 | 88.88 | 77 | PASS |
| prior_open_midday_large20_reclaim_reversion_1400 | 9 | 0 | 47.35 | 57.09 | 51 | FAIL |
| prior_open_morning_signed_reclaim_reversion_1130 | 9 | 9 | 66.52 | 62.93 | 67 | PASS |

Machine summary:

```json
{
  "all_rows_density_pass": false,
  "audit_date": "2026-06-30",
  "campaign_id": "nq_prior_session_benchmark_orderflow_reaction",
  "declared_entry_rows": 45,
  "density_fail_rows": 9,
  "density_pass_rows": 36,
  "failed_variants": [
    "prior_open_midday_large20_reclaim_reversion_1400"
  ],
  "full_end_date": "2026-06-12",
  "full_sessions": 3813,
  "full_start_date": "2011-01-03",
  "latest_252_end_date": "2026-06-12",
  "latest_252_start_date": "2025-06-09",
  "limited_end_date": "2012-09-07",
  "limited_start_date": "2011-02-22",
  "min_full_signals_per_year": 47.348421705976236,
  "min_latest_252_signals": 51,
  "min_limited_signals_per_year": 57.09058614564831,
  "prepared_rows": 297414,
  "source_campaign_id": "es_prior_session_benchmark_orderflow_reaction",
  "verdict": "FAIL"
}
```

Detail CSV: `research_artifacts/nq_prior_session_benchmark_orderflow_reaction_density_audit_20260630.csv`

Summary CSV: `research_artifacts/nq_prior_session_benchmark_orderflow_reaction_density_summary_20260630.csv`

Verdict: FAIL.
