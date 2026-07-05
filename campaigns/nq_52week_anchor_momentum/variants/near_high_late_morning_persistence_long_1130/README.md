# near_high_late_morning_persistence_long_1130

Campaign: `nq_52week_anchor_momentum`

Mechanic: Prior close is in a broad top-ranked 52-week-high anchor band, then late-morning completed price action remains positive at 11:30 ET.

Entry module: `fifty_two_week_anchor_momentum`. The module uses only completed prior RTH daily bars for the 252-session anchor and emits no earlier than a completed 5-minute signal bar.

Stop module: `percent_from_entry`. Take-profit module: `fixed_r`.
