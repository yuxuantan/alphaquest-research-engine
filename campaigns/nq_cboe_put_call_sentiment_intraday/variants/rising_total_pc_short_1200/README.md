# rising_total_pc_short_1200

Campaign: `nq_cboe_put_call_sentiment_intraday`

Mechanic: At 12:00:00 ET, short NQ when latest prior total Cboe put/call ratio one-day change rank is in the upper tail; flatten by 15:55 unless stop/target is hit.

Feature timing: `data/external/nq_cboe_put_call_features_20110103_20260612.csv` uses only Cboe observations strictly before the NQ session date.

Entry module: `cboe_put_call_sentiment`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.
