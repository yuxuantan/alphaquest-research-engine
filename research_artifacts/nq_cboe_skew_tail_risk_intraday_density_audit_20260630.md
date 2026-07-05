# NQ Cboe SKEW Tail-Risk Intraday Density Audit

Created: 2026-06-30

This audit uses the NQ RTH bar cache and `data/external/nq_cboe_skew_tail_risk_features_20110103_20260612.csv` before any NQ PnL inspection. The feature file uses the latest Cboe SKEW close strictly before the NQ session date.

| Variant | Threshold | Signals | Signals/year | Pass |
| --- | --- | ---: | ---: | --- |
| `high_skew_short_1000` | skew_rank_min=0.55 | 1828 | 118.403440 | yes |
| `high_skew_short_1000` | skew_rank_min=0.60 | 1655 | 107.197863 | yes |
| `high_skew_short_1000` | skew_rank_min=0.65 | 1503 | 97.352500 | yes |
| `low_skew_long_1030` | skew_rank_max=0.45 | 1601 | 103.700168 | yes |
| `low_skew_long_1030` | skew_rank_max=0.40 | 1426 | 92.365047 | yes |
| `low_skew_long_1030` | skew_rank_max=0.35 | 1282 | 83.037861 | yes |
| `rising_skew_short_1130` | skew_change_rank_min=0.55 | 1701 | 110.177381 | yes |
| `rising_skew_short_1130` | skew_change_rank_min=0.60 | 1513 | 98.000222 | yes |
| `rising_skew_short_1130` | skew_change_rank_min=0.65 | 1326 | 85.887835 | yes |
| `falling_skew_long_1200` | skew_change_rank_max=0.45 | 1681 | 108.881938 | yes |
| `falling_skew_long_1200` | skew_change_rank_max=0.40 | 1478 | 95.733197 | yes |
| `falling_skew_long_1200` | skew_change_rank_max=0.35 | 1299 | 84.138987 | yes |
| `persistent_high_skew_short_1330` | skew_mean_rank_min=0.55 | 1818 | 117.755719 | yes |
| `persistent_high_skew_short_1330` | skew_mean_rank_min=0.60 | 1659 | 107.456952 | yes |
| `persistent_high_skew_short_1330` | skew_mean_rank_min=0.65 | 1506 | 97.546817 | yes |

Pre-PnL decision: approve all five variants for staged testing. Every declared threshold corner clears the 50 signals/year density gate. No PnL, net profit, drawdown, or trade outcome was inspected.
