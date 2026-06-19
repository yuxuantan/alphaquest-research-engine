# ES Key Reversal Orderflow Density Audit

Purpose: pre-PnL trade-density check before staged backtests.

Full-history subset: 2011-01-03 to 2026-06-09
Limited-core resolved random 10% subset: 2011-02-22 to 2012-09-06

Final predeclared entry grid counted only signal-affecting parameters: `min_sweep_ticks` in `[1, 2]` x `min_orderflow_imbalance` in `[0.0, 0.02, 0.04]`. Stop and target grids do not affect signal frequency.

The initial 5-minute formulation and the 1-minute grid including a 3-tick sweep were rejected before PnL because they could not keep all variants above the 50 signals/year density floor in the limited-core window.

## Summary

| variant_id | full_min_signals_per_year | limited_min_signals_per_year | passed_density_floor |
| --- | --- | --- | --- |
| afternoon_large20_two_sided_key_reversal_1530 | 168.01 | 94.07 | True |
| late_morning_large10_down_sweep_reclaim_long_1230 | 166.59 | 81.74 | True |
| late_morning_large10_up_sweep_reject_short_1230 | 165.49 | 83.04 | True |
| midday_signed_two_sided_key_reversal_1400 | 162.57 | 83.69 | True |
| morning_signed_two_sided_key_reversal_1130 | 190.89 | 125.86 | True |

Detailed CSV: `research_artifacts/es_key_reversal_orderflow_reversal_density_audit_20260619.csv`
