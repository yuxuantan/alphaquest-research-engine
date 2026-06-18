# es_prior_value_area_orderflow_rejection Density Audit

- Generated: 2026-06-18
- Source: local Sierra aggregate orderflow parquet only
- Full configured subset: 2011-01-03 to 2026-06-09 (15.43 years)
- Limited-core subset: 2011-02-22 to 2012-09-06 (1.54 years)
- Limited-core window policy: seeded random contiguous 10% of configured data, avoiding the latest 10% and 2020-02-01 through 2021-06-30.
- Density requirement used before PnL: every tested entry parameter expression must plausibly support >= 50 raw module signals/year on full and limited-core data.
- Pre-PnL grid adjustment: `morning_signed_vah_rejection_short` removed `entry.params.rejection_buffer_ticks: 2` before any PnL because that one buffer value fell below the limited-core density floor. No mechanic, stop, target, data window, costs, or validation gate changed.
- Caveat found during staged testing: this audit counts raw entry-module signals while flat-state position overlap is ignored. The staged `limited_core_grid_test` summaries are authoritative for tradable signal density because the engine suppresses new signals while a position is already open.

| variant | tested entry combos | total grid combos | min full signals/year | max full signals/year | min limited signals/year | max limited signals/year | entry combos passing both | decision |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| afternoon_large20_two_sided_rejection | 9 | 81 | 69.20 | 83.59 | 55.14 | 78.50 | 9/9 | PASS_DENSITY |
| late_morning_signed_two_sided_rejection | 9 | 81 | 77.75 | 97.71 | 66.17 | 84.99 | 9/9 | PASS_DENSITY |
| midday_large10_two_sided_rejection | 9 | 81 | 67.97 | 85.21 | 59.04 | 82.39 | 9/9 | PASS_DENSITY |
| morning_signed_vah_rejection_short | 6 | 54 | 60.91 | 73.67 | 51.90 | 59.04 | 6/6 | PASS_DENSITY |
| morning_signed_val_rejection_long | 9 | 81 | 52.10 | 68.68 | 51.25 | 63.58 | 9/9 | PASS_DENSITY |

## Decision

RAW_MODULE_DENSITY_PASS: all current tested variants and entry parameter expressions met the pre-PnL raw signal-frequency floor on both full and limited-core data. Staged limited-core `signal_density` remains the authoritative tradable-frequency evidence.

Detailed rows: `research_artifacts/es_prior_value_area_orderflow_rejection_density_audit_20260618.csv`
