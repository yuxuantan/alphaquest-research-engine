# NQ Realized Skewness Reversal Density Audit

Created: 2026-06-30

This audit was completed before any NQ PnL staged run for `nq_realized_skewness_reversal`. It counts possible one-signal-per-session entries from the lagged NQ realized-skewness feature file across the declared threshold grid.

Feature file: `data/external/nq_lagged_realized_skewness_features_20110103_20260612.csv`

Date range: 2011-01-03 through 2026-06-12

## Result

All five variant shapes clear the 50 signals/year pre-PnL density floor.

| Variant | Rank column | Tail | Minimum signals/year |
| --- | --- | --- | ---: |
| low_1d_skew_open_long_1000 | skew1_rank_252 | low | 60.82 |
| high_1d_skew_open_short_1000 | skew1_rank_252 | high | 62.96 |
| low_3d_skew_midmorning_long_1030 | skew3_rank_252 | low | 61.27 |
| high_3d_skew_midday_short_1200 | skew3_rank_252 | high | 63.74 |
| two_sided_5d_skew_extreme_1330 | skew5_rank_252 | two-sided | 123.84 |

The detailed threshold counts are in `research_artifacts/nq_realized_skewness_reversal_density_audit_20260630.csv`.
