# midday_trend_reclaim_two_sided

This variant trades the VWAP pullback-continuation edge in the midday window. From 11:30 through 14:00 ET, it enters with the prevailing VWAP-side trend after a completed pullback reclaim.

Tunable parameters are fixed before testing: two entry parameters, percent stop, and fixed-R target.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_vwap_pullback_continuation/midday_trend_reclaim_two_sided/run1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.
