# NQ Consumer Sentiment State Intraday Density Audit

Created: 2026-06-30

This audit uses the NQ RTH bar cache and `data/external/nq_consumer_sentiment_features_20110103_20260612.csv` before any NQ PnL inspection. The feature file uses only UMCSENT observations available at least 45 calendar days before each NQ session date.

| Variant | Threshold | Signals | Signals/year | Pass |
| --- | --- | ---: | ---: | --- |
| `low_sentiment_long_1000` | sentiment_rank_max=0.45 | 1978 | 128.119259 | yes |
| `low_sentiment_long_1000` | sentiment_rank_max=0.40 | 1876 | 121.512502 | yes |
| `low_sentiment_long_1000` | sentiment_rank_max=0.35 | 1775 | 114.970518 | yes |
| `high_sentiment_short_1030` | sentiment_rank_min=0.55 | 1670 | 108.169445 | yes |
| `high_sentiment_short_1030` | sentiment_rank_min=0.60 | 1567 | 101.497916 | yes |
| `high_sentiment_short_1030` | sentiment_rank_min=0.65 | 1429 | 92.559363 | yes |
| `rising_sentiment_long_1130` | sentiment_change_rank_min=0.55 | 1683 | 109.011483 | yes |
| `rising_sentiment_long_1130` | sentiment_change_rank_min=0.60 | 1532 | 99.230892 | yes |
| `rising_sentiment_long_1130` | sentiment_change_rank_min=0.65 | 1303 | 84.398076 | yes |
| `falling_sentiment_short_1200` | sentiment_change_rank_max=0.45 | 1736 | 112.444405 | yes |
| `falling_sentiment_short_1200` | sentiment_change_rank_max=0.40 | 1446 | 93.660489 | yes |
| `falling_sentiment_short_1200` | sentiment_change_rank_max=0.35 | 1255 | 81.289014 | yes |
| `low_sentiment_ma_long_1330` | sentiment_ma_rank_max=0.45 | 1889 | 122.354540 | yes |
| `low_sentiment_ma_long_1330` | sentiment_ma_rank_max=0.40 | 1791 | 116.006872 | yes |
| `low_sentiment_ma_long_1330` | sentiment_ma_rank_max=0.35 | 1731 | 112.120544 | yes |

Pre-PnL decision: approve all five variants for staged testing. Every declared threshold corner clears the 50 signals/year density gate. No PnL, net profit, drawdown, or trade outcome was inspected.
