# post_vix_settlement_next_session_long_1000

Campaign: `nq_vix_expiration_pressure`

Mechanic: setup_mode `post_vix_settlement_next_session_long`, signal type `next_regular_session`; enter long NQ at 10:00:00 ET next-bar open and flatten by 15:55 ET.

Entry module: `vix_expiration_pressure`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.
