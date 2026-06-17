# ES EPU Policy Uncertainty Intraday Density Audit - 2026-06-16

Decision: PASS density gate before performance testing.

Scope: `campaigns/es_epu_policy_uncertainty_intraday`.

Data:
- ES bars: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- EPU source: free public Daily U.S. EPU CSV from `https://www.policyuncertainty.com/media/All_Daily_Policy_Data.csv`
- Feature file: `data/external/es_epu_policy_uncertainty_features_20110103_20260609.csv`
- Feature rows: `3817`
- Valid ranked rows: `3760`
- Session range: `2011-01-03` to `2026-06-09`
- Availability rule: latest Daily EPU observation on or before `session_date - 30 calendar days`

Rationale for the 30-day lag:
- The Daily U.S. EPU source states that recent daily observations can be revised as newspaper coverage updates.
- This campaign therefore treats only observations at least 30 calendar days old as available to the ES intraday signal.

Declared entry-density check:

| Variant | Driver | Threshold | Signal days | Approx trades/year |
| --- | --- | ---: | ---: | ---: |
| high_epu_short_1000 | epu_index_rank_252 >= | 0.55 | 1712 | 110.95 |
| high_epu_short_1000 | epu_index_rank_252 >= | 0.60 | 1537 | 99.61 |
| high_epu_short_1000 | epu_index_rank_252 >= | 0.65 | 1363 | 88.33 |
| low_epu_long_1030 | epu_index_rank_252 <= | 0.45 | 1692 | 109.65 |
| low_epu_long_1030 | epu_index_rank_252 <= | 0.40 | 1518 | 98.38 |
| low_epu_long_1030 | epu_index_rank_252 <= | 0.35 | 1338 | 86.71 |
| rising_epu_short_1130 | epu_change_5d_rank_252 >= | 0.55 | 1719 | 111.40 |
| rising_epu_short_1130 | epu_change_5d_rank_252 >= | 0.60 | 1530 | 99.15 |
| rising_epu_short_1130 | epu_change_5d_rank_252 >= | 0.65 | 1343 | 87.04 |
| falling_epu_long_1200 | epu_change_5d_rank_252 <= | 0.45 | 1676 | 108.62 |
| falling_epu_long_1200 | epu_change_5d_rank_252 <= | 0.40 | 1490 | 96.56 |
| falling_epu_long_1200 | epu_change_5d_rank_252 <= | 0.35 | 1323 | 85.74 |
| high_epu_ma_short_1330 | epu_ma_20_rank_252 >= | 0.55 | 1648 | 106.80 |
| high_epu_ma_short_1330 | epu_ma_20_rank_252 >= | 0.60 | 1483 | 96.11 |
| high_epu_ma_short_1330 | epu_ma_20_rank_252 >= | 0.65 | 1304 | 84.51 |

Conclusion:
- All five original variants are dense enough to test under the user's `>=50 trades/year` rule.
- No performance result was inspected before finalizing the original parameter spaces.
