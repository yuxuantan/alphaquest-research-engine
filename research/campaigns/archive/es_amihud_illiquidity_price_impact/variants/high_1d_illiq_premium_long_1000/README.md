# high_1d_illiq_premium_long_1000

Mechanic: At 10:00 ET, long ES when the prior completed RTH session's Amihud illiquidity rank is in the high tail; flatten by 15:55 ET unless stop or target is hit.

Signal state is computed from `data/external/es_amihud_illiquidity_features_20110103_20260609.csv`, where every tradable Amihud illiquidity field is shifted one completed RTH session. The entry signal is evaluated on the completed 1-minute bar immediately before the configured entry time, so fills occur no earlier than the next bar open.

Stop module: `percent_from_entry`. Target module: `fixed_r`. No overnight exposure is allowed.
