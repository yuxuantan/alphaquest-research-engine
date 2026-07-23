# nq_aqr_bab_factor_state Pre-PnL Density Audit

Date: 2026-06-22

This audit counts only lagged AQR BAB rank-state signal eligibility for the declared NQ port before any NQ PnL was inspected.
Feature CSV: `data/external/nq_aqr_bab_features_20110103_20260612.csv`.
Window: 2011-01-03 through 2026-06-12; elapsed calendar years: 15.4387.

Decision: PASS. Every declared BAB threshold setting is above the 50 signals/year pre-PnL density floor.

## Variant Summary

| variant_id | min | max | mean |
| --- | --- | --- | --- |
| bab_63d_extreme_two_sided_1330 | 62.505098 | 82.843545 | 72.825457 |
| low_bab_21d_rebound_long_1000 | 60.497163 | 70.925474 | 65.894840 |
| low_bab_63d_rebound_long_1030 | 60.821023 | 71.702740 | 66.456198 |
| low_bab_daily_rebound_long_0935 | 58.553999 | 70.407297 | 64.383490 |
| low_bab_z63_rebound_long_1100 | 59.914214 | 69.565260 | 64.340309 |

## Controls

- Each NQ session uses only the latest AQR BAB observation at least 45 calendar days old.
- Signal state is keyed by session date before the fixed intraday entry time.
- The density audit does not inspect NQ trade outcomes, PnL, selected best parameters, or equity curves.
