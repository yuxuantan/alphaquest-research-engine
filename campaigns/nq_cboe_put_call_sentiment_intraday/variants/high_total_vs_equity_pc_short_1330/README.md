# high_total_vs_equity_pc_short_1330

Campaign: `nq_cboe_put_call_sentiment_intraday`

Mechanic: At 13:30:00 ET, short NQ when latest prior total-minus-equity put/call spread rank is high; flatten by 15:55 unless stop/target is hit.

Feature timing: `data/external/nq_cboe_put_call_features_20110103_20260612.csv` uses only Cboe observations strictly before the NQ session date.

Entry module: `cboe_put_call_sentiment`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.
