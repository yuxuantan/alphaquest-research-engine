# vix_settlement_open_pressure_short_1000

Campaign: `nq_vix_expiration_pressure`

Mechanic: setup_mode `vix_settlement_open_pressure_short`, signal type `vix_expiration_session`; enter short NQ at 10:00:00 ET next-bar open and flatten by 15:55 ET.

Entry module: `vix_expiration_pressure`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.
