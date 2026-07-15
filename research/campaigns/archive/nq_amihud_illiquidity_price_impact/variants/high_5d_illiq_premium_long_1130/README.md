# high_5d_illiq_premium_long_1130

Mechanic: At 11:30 ET, long NQ when the prior 5-session average Amihud illiquidity rank is in the high tail; flatten by 15:55 ET unless stop or target is hit.

Signal state is computed from `data/external/nq_amihud_illiquidity_features_20110103_20260612.csv`, where every tradable Amihud illiquidity field is shifted one completed NQ RTH session. The entry signal is evaluated on the completed 1-minute bar immediately before the configured entry time, so fills occur no earlier than the next bar open.
