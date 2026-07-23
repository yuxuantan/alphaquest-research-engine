# es_morning_trend_lunch_reversal_orderflow Density Audit

- Generated: 2026-06-18
- Source: local Sierra aggregate orderflow parquet only
- Full configured subset: 2011-01-03 to 2026-06-09 (15.43 years), rows=297,726
- Limited-core subset: 2011-02-22 to 2012-09-06 (1.54 years), rows=29,172
- Count type: raw module signals, at most one per session; staged limited-core signal_density remains authoritative for tradable signals after open-position suppression.

| variant | min full signals/year | max full signals/year | min limited signals/year | max limited signals/year | entry combos passing both | decision |
|---|---:|---:|---:|---:|---:|---|
| early_afternoon_large20_two_sided_reversal_1400 | 194.64 | 228.53 | 167.38 | 219.93 | 9/9 | RAW_DENSITY_PASS |
| late_morning_signed_down_extension_long_1130 | 84.23 | 115.46 | 73.31 | 107.69 | 9/9 | RAW_DENSITY_PASS |
| late_morning_signed_up_extension_short_1130 | 94.34 | 126.74 | 77.85 | 110.29 | 9/9 | RAW_DENSITY_PASS |
| lunch_large10_two_sided_reversal_1300 | 195.49 | 231.84 | 164.14 | 218.63 | 9/9 | RAW_DENSITY_PASS |
| lunch_signed_two_sided_reversal_1230 | 182.33 | 226.13 | 153.76 | 208.25 | 9/9 | RAW_DENSITY_PASS |

## Decision

RAW_MODULE_DENSITY_PASS: proceed to preflight and staged validation without changing mechanics.

Detailed rows: `research_artifacts/es_morning_trend_lunch_reversal_orderflow_density_audit_20260618.csv`
