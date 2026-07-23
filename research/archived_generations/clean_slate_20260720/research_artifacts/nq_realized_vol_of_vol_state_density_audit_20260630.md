# NQ Realized Volatility-of-Volatility State Density Audit

Created: 2026-06-30

This audit was completed before any NQ PnL staged run for `nq_realized_vol_of_vol_state`. It counts possible one-signal-per-session entries from the lagged NQ realized volatility-of-volatility feature file across the declared threshold grid.

Feature file: `data/external/nq_realized_vol_of_vol_features_20110103_20260612.csv`

Date range: 2011-01-03 through 2026-06-12

## Result

All five variant shapes clear the 50 signals/year pre-PnL density floor.

| Variant | Rank column | Tail | Minimum signals/year |
| --- | --- | --- | ---: |
| high_1d_vov_premium_long_1000 | intraday_vov1_rank_252 | high | 66.13 |
| high_1d_vov_stress_short_1030 | intraday_vov1_rank_252 | high | 66.13 |
| low_1d_vov_calm_long_1130 | intraday_vov1_rank_252 | low | 59.53 |
| high_5d_vov_premium_long_1200 | intraday_vov5_rank_252 | high | 69.50 |
| two_sided_20d_vov_state_1330 | intraday_vov20_rank_252 | two-sided | 132.39 |

The detailed threshold counts are in `research_artifacts/nq_realized_vol_of_vol_state_density_audit_20260630.csv`.
