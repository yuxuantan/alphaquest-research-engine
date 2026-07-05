# nq_prior_level_delta_dislocation density audit

- Audit date: 2026-06-30
- Full window: 2011-01-03 to 2026-06-12 (3813 sessions)
- Limited-core window: 2011-02-22 to 2012-09-07
- Latest-252 window: 2025-06-09 to 2026-06-12
- Exact-transfer max distance: 32 ticks
- Declared entry rows: 45
- Density passes: 0
- Density failures: 45

Gate: each declared entry row must produce at least 50 signals/year in full history, at least 50 signals/year in the limited-core window, and at least 50 signals in the latest 252 sessions before any PnL is inspected.

| variant | rows | pass rows | min full/year | max full/year | min limited/year | max latest-252 | verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| pdh_buy_absorption_long | 9 | 0 | 1.62 | 7.32 | 5.19 | 0 | FAIL |
| pdh_buy_exhaustion_short | 9 | 0 | 1.62 | 7.32 | 5.19 | 0 | FAIL |
| pdl_sell_absorption_long | 9 | 0 | 1.49 | 4.66 | 2.60 | 3 | FAIL |
| pdl_sell_pressure_short | 9 | 0 | 1.49 | 4.66 | 2.60 | 3 | FAIL |
| two_sided_auto_level_fade | 9 | 0 | 2.79 | 10.23 | 7.14 | 3 | FAIL |

Sensitivity by fixed max-distance cap:

| max distance ticks | pass rows | max full/year | max latest-252 | all rows pass |
|---:|---:|---:|---:|---|
| 16 | 0 | 5.83 | 0 | False |
| 32 | 0 | 10.23 | 3 | False |
| 48 | 0 | 13.41 | 3 | False |
| 64 | 0 | 16.65 | 3 | False |
| 96 | 0 | 21.96 | 6 | False |
| 128 | 0 | 25.65 | 7 | False |
| none | 0 | 42.04 | 47 | False |

Machine summary:

```json
{
  "all_rows_density_pass": false,
  "audit_date": "2026-06-30",
  "declared_entry_rows": 45,
  "density_fail_rows": 45,
  "density_pass_rows": 0,
  "edge_id": "nq_prior_level_delta_dislocation",
  "failed_variants": [
    "pdh_buy_absorption_long",
    "pdh_buy_exhaustion_short",
    "pdl_sell_absorption_long",
    "pdl_sell_pressure_short",
    "two_sided_auto_level_fade"
  ],
  "full_end_date": "2026-06-12",
  "full_sessions": 3813,
  "full_start_date": "2011-01-03",
  "latest_252_end_date": "2026-06-12",
  "latest_252_start_date": "2025-06-09",
  "limited_end_date": "2012-09-07",
  "limited_start_date": "2011-02-22",
  "min_full_signals_per_year": 1.4897588224862564,
  "min_latest_252_signals": 0,
  "min_limited_signals_per_year": 2.5950266429840143,
  "prepared_rows": 1487070,
  "sensitivity_best_density_pass_rows": 0,
  "sensitivity_best_max_distance_ticks": null,
  "sensitivity_best_max_full_signals_per_year": 42.03710764319915,
  "sensitivity_best_max_latest_252_signals": 47,
  "verdict": "FAIL",
  "verdict_reason": "pre-PnL density rejection; exact ES-transfer grid and no-cap sensitivity are below signal-count gates"
}
```

Detail CSV: `research_artifacts/nq_prior_level_delta_dislocation_density_audit_20260630.csv`

Summary CSV: `research_artifacts/nq_prior_level_delta_dislocation_density_summary_20260630.csv`

Sensitivity CSV: `research_artifacts/nq_prior_level_delta_dislocation_density_sensitivity_20260630.csv`

Verdict: FAIL.
