# ES Consumer Sentiment State Intraday Density Audit - 2026-06-16

Decision: PASS density gate before performance testing.

Scope: `campaigns/es_consumer_sentiment_state_intraday`.

Data:
- ES bars: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Sentiment source: free public FRED/University of Michigan `UMCSENT` CSV from `https://fred.stlouisfed.org/graph/fredgraph.csv?id=UMCSENT`
- Feature file: `data/external/es_consumer_sentiment_features_20110103_20260609.csv`
- Feature rows: `3817`
- Valid ranked rows: `3817`
- Session range: `2011-01-03` to `2026-06-09`
- Availability rule: latest UMCSENT observation on or before `session_date - 45 calendar days`

Rationale for the 45-day lag:
- FRED states the University of Michigan consumer-sentiment series is delayed by one month at the request of the source.
- This campaign therefore treats only observations at least 45 calendar days old as available to the ES intraday signal.
- Monthly rolling ranks are computed on monthly observations before merging into ES daily sessions.

Declared entry-density check:

| Variant | Driver | Threshold | Signal days | Approx trades/year |
| --- | --- | ---: | ---: | ---: |
| low_sentiment_long_1000 | consumer_sentiment_rank_120m <= | 0.45 | 1983 | 128.51 |
| low_sentiment_long_1000 | consumer_sentiment_rank_120m <= | 0.40 | 1880 | 121.84 |
| low_sentiment_long_1000 | consumer_sentiment_rank_120m <= | 0.35 | 1776 | 115.10 |
| high_sentiment_short_1030 | consumer_sentiment_rank_120m >= | 0.55 | 1670 | 108.23 |
| high_sentiment_short_1030 | consumer_sentiment_rank_120m >= | 0.60 | 1568 | 101.62 |
| high_sentiment_short_1030 | consumer_sentiment_rank_120m >= | 0.65 | 1428 | 92.54 |
| rising_sentiment_long_1130 | sentiment_change_3m_rank_120m >= | 0.55 | 1685 | 109.20 |
| rising_sentiment_long_1130 | sentiment_change_3m_rank_120m >= | 0.60 | 1534 | 99.41 |
| rising_sentiment_long_1130 | sentiment_change_3m_rank_120m >= | 0.65 | 1305 | 84.57 |
| falling_sentiment_short_1200 | sentiment_change_3m_rank_120m <= | 0.45 | 1737 | 112.57 |
| falling_sentiment_short_1200 | sentiment_change_3m_rank_120m <= | 0.40 | 1447 | 93.78 |
| falling_sentiment_short_1200 | sentiment_change_3m_rank_120m <= | 0.35 | 1256 | 81.40 |
| low_sentiment_ma_long_1330 | sentiment_ma_12_rank_120m <= | 0.45 | 1891 | 122.55 |
| low_sentiment_ma_long_1330 | sentiment_ma_12_rank_120m <= | 0.40 | 1793 | 116.20 |
| low_sentiment_ma_long_1330 | sentiment_ma_12_rank_120m <= | 0.35 | 1733 | 112.31 |

Conclusion:
- All five original variants are dense enough to test under the user's `>=50 trades/year` rule.
- No performance result was inspected before finalizing the original parameter spaces.
