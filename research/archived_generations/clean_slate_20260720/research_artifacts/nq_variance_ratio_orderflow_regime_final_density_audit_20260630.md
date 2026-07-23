# NQ Variance-Ratio Orderflow Regime Final Density Audit - 2026-06-30

Verdict: PASS before staged PnL.

No NQ PnL, stop/target outcome, trade net, or benchmark result was inspected. This final audit follows the documented pre-PnL density-only reformulation of sparse flow-imbalance corners.

Prepared rows: 297414.
Session span: 2011-01-03 through 2026-06-12 (15.439 years).
Latest-session density window: last 252 sessions.

## Reformulation

- `afternoon_high_vr_signed_continuation_1530`: `entry.params.min_orderflow_imbalance` grid changed from `[0.02, 0.05, 0.08]` to `[0.015, 0.035, 0.05]`.
- `morning_high_vr_signed_continuation_1130`: `entry.params.min_orderflow_imbalance` grid changed from `[0.01, 0.025, 0.04]` to `[0.01, 0.02, 0.025]`.
- `morning_low_vr_signed_reversion_1130`: `entry.params.min_orderflow_imbalance` grid changed from `[0.02, 0.04, 0.06]` to `[0.005, 0.01, 0.02]`.

VR thresholds, directions, time windows, stop/target grids, costs, data, and stage gates were unchanged.

## Variant Summary

| variant_id | entry_combos | min_full_signals_per_year | min_latest_252_signals | full_failures | latest_failures |
| --- | --- | --- | --- | --- | --- |
| afternoon_high_vr_signed_continuation_1530 | 9 | 152.991754 | 121 | 0 | 0 |
| midday_high_vr_large10_continuation_1400 | 9 | 176.763123 | 200 | 0 | 0 |
| midday_low_vr_large10_reversion_1430 | 9 | 276.641736 | 311 | 0 | 0 |
| morning_high_vr_signed_continuation_1130 | 9 | 72.544777 | 69 | 0 | 0 |
| morning_low_vr_signed_reversion_1130 | 9 | 106.485370 | 85 | 0 | 0 |

All declared entry-grid combinations cleared both density checks: at least 50 full-history signals per year and at least 50 signals in the latest 252 sessions.
