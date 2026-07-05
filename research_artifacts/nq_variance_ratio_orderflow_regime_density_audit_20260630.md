# NQ Variance-Ratio Orderflow Regime Density Audit - 2026-06-30

Verdict: FAIL before staged PnL.

No NQ PnL, stop/target outcome, trade net, or benchmark result was inspected. This audit counts only entry-module signal opportunities on prepared 5-minute NQ bars.

## Variant Summary

| variant_id | entry_combos | min_full_signals_per_year | min_latest_252_signals | full_failures | latest_failures |
| --- | --- | --- | --- | --- | --- |
| afternoon_high_vr_signed_continuation_1530 | 9 | 93.790034 | 40 | 0 | 2 |
| midday_high_vr_large10_continuation_1400 | 9 | 176.763123 | 200 | 0 | 0 |
| midday_low_vr_large10_reversion_1430 | 9 | 276.641736 | 311 | 0 | 0 |
| morning_high_vr_signed_continuation_1130 | 9 | 55.250621 | 40 | 0 | 1 |
| morning_low_vr_signed_reversion_1130 | 9 | 41.907563 | 14 | 1 | 4 |

At least one declared entry-grid combination failed density. Under fail-closed research rules this campaign should not proceed to staged PnL without an explicit pre-PnL reformulation decision.

## Failing Rows

| variant_id | entry_combo | signals_per_year_full | signals_latest_252_sessions |
| --- | --- | --- | --- |
| afternoon_high_vr_signed_continuation_1530 | entry.params.vr_threshold=1.05,entry.params.min_orderflow_imbalance=0.08 | 120.411376 | 48 |
| afternoon_high_vr_signed_continuation_1530 | entry.params.vr_threshold=1.15,entry.params.min_orderflow_imbalance=0.08 | 93.790034 | 40 |
| morning_high_vr_signed_continuation_1130 | entry.params.vr_threshold=1.15,entry.params.min_orderflow_imbalance=0.04 | 55.250621 | 40 |
| morning_low_vr_signed_reversion_1130 | entry.params.vr_threshold=0.95,entry.params.min_orderflow_imbalance=0.04 | 68.399362 | 44 |
| morning_low_vr_signed_reversion_1130 | entry.params.vr_threshold=0.95,entry.params.min_orderflow_imbalance=0.06 | 41.907563 | 14 |
| morning_low_vr_signed_reversion_1130 | entry.params.vr_threshold=1.05,entry.params.min_orderflow_imbalance=0.06 | 50.910888 | 18 |
| morning_low_vr_signed_reversion_1130 | entry.params.vr_threshold=1.15,entry.params.min_orderflow_imbalance=0.06 | 58.424455 | 21 |
