# ES Key Reversal Orderflow Density Audit

Purpose: pre-PnL trade-density check before staged backtests.

Full-history subset: 2011-01-03 to 2026-06-09
Limited-core resolved random 10% subset: 2011-02-22 to 2012-09-06
Full strategy bars: 297,726; limited strategy bars: 29,172

Entry grid counted only signal-affecting parameters: `min_sweep_ticks` x `min_orderflow_imbalance`. Stop and target grids do not affect signal frequency.

## Summary

| variant_id | full_min_signals_per_year | limited_min_signals_per_year | passed_density_floor |
| --- | --- | --- | --- |
| afternoon_large20_two_sided_key_reversal_1530 | 82.94 | 25.95 | False |
| late_morning_large10_down_sweep_reclaim_long_1230 | 45.49 | 15.57 | False |
| late_morning_large10_up_sweep_reject_short_1230 | 35.12 | 12.33 | False |
| midday_signed_two_sided_key_reversal_1400 | 49.83 | 16.87 | False |
| morning_signed_two_sided_key_reversal_1130 | 56.05 | 26.60 | False |

Detailed CSV: `research_artifacts/es_key_reversal_orderflow_reversal_density_audit_20260619.csv`
