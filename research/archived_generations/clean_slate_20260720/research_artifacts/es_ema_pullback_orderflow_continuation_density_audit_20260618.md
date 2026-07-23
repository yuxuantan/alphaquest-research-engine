# ES EMA Pullback Orderflow Continuation Density Audit

- Created: 2026-06-18
- Campaign: `es_ema_pullback_orderflow_continuation`
- Count type: vectorized raw entry signals, capped at first signal per session to match max one trade/day intent; staged limited-core `signal_density` remains authoritative for tradable signals after engine position suppression.
- Data: local Sierra ES 1-minute aggregate-orderflow cache, resampled to 5-minute bars by the repo pipeline.
- Full sample: `2011-01-03` to `2026-06-09`.
- Limited-core benchmark subset: `2011-02-22` to `2012-09-06`.

RAW_MODULE_DENSITY_STATUS: raw_module_density_passed

## Variant Summary

| variant_id | min_full_signals_per_year | max_full_signals_per_year | min_limited_core_signals_per_year | max_limited_core_signals_per_year | failing_entry_combos |
| --- | --- | --- | --- | --- | --- |
| afternoon_large10_two_sided_ema_pullback_1430 | 167.69 | 242.46 | 120.67 | 239.39 | 0 |
| late_morning_signed_long_ema_pullback_1200 | 99.27 | 166.72 | 83.04 | 166.08 | 0 |
| late_morning_signed_short_ema_pullback_1200 | 86.5 | 146.83 | 84.99 | 149.86 | 0 |
| late_morning_signed_two_sided_ema_pullback_1130 | 144.04 | 230.28 | 134.94 | 234.2 | 0 |
| lunch_signed_two_sided_ema_pullback_1300 | 160.17 | 241.36 | 120.02 | 232.9 | 0 |

Detailed rows: `research_artifacts/es_ema_pullback_orderflow_continuation_density_audit_20260618.csv`
