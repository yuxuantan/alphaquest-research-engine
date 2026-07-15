# high_goodvol_fade_short_1200

Mechanic: At 12:00 ET, short ES when prior-session upside realized semivariance rank is high; flatten by 15:55 ET unless stop or target is hit.

Signal state is computed from `data/external/es_realized_semivariance_features_20110103_20260609.csv`, where every tradable semivariance field is shifted one completed RTH session. The entry signal is evaluated on the completed 1-minute bar immediately before the configured entry time, so fills occur no earlier than the next bar open.

Stop module: `percent_from_entry`. Target module: `fixed_r`. No overnight exposure is allowed.
