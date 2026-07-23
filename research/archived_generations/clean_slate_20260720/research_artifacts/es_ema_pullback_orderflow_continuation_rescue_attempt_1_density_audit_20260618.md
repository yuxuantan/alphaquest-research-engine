# ES EMA Pullback Orderflow Continuation Rescue Density Audit

- Created: 2026-06-18
- Rescue: parameter_space_rescue_1
- Count type: vectorized raw entry signals, capped at first signal per session; staged signal_density remains authoritative.
- Rescue changes only fixed parameters and parameter space; no PnL used in this density gate.

RAW_MODULE_DENSITY_STATUS: raw_module_density_passed

## Variant Summary

| variant_id | min_full_signals_per_year | max_full_signals_per_year | min_limited_core_signals_per_year | max_limited_core_signals_per_year | failing_entry_combos |
| --- | --- | --- | --- | --- | --- |
| afternoon_large10_two_sided_ema_pullback_1430 | 140.41 | 195.42 | 84.34 | 153.76 | 0 |
| late_morning_signed_long_ema_pullback_1200 | 79.7 | 127.84 | 55.14 | 101.21 | 0 |
| late_morning_signed_short_ema_pullback_1200 | 72.25 | 111.25 | 66.82 | 108.34 | 0 |
| late_morning_signed_two_sided_ema_pullback_1130 | 117.73 | 184.54 | 100.56 | 167.38 | 0 |
| lunch_signed_two_sided_ema_pullback_1300 | 133.35 | 196.2 | 83.69 | 156.35 | 0 |

Detailed rows: `research_artifacts/es_ema_pullback_orderflow_continuation_rescue_attempt_1_density_audit_20260618.csv`
