# near_high_pullback_reclaim_long_1200

Campaign: `nq_52week_anchor_momentum`

Mechanic: Prior close is in the 52-week-high anchor band, price makes a completed intraday pullback, then reclaims the prior close before noon.

Entry module: `fifty_two_week_anchor_momentum`. The module uses only completed prior RTH daily bars for the 252-session anchor and emits no earlier than a completed 5-minute signal bar.

Stop module: `percent_from_entry`. Take-profit module: `fixed_r`.
