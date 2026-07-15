# near_high_extension_hold_long_1130

Campaign: `nq_52week_anchor_momentum`

Mechanic: Prior close is in the 52-week-high anchor band, the session extends above the prior close by a predeclared amount, and price remains positive at 11:30 ET.

Entry module: `fifty_two_week_anchor_momentum`. The module uses only completed prior RTH daily bars for the 252-session anchor and emits no earlier than a completed 5-minute signal bar.

Stop module: `percent_from_entry`. Take-profit module: `fixed_r`.
