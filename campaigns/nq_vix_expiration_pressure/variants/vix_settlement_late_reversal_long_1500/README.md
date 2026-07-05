# vix_settlement_late_reversal_long_1500

Campaign: `nq_vix_expiration_pressure`

Mechanic: setup_mode `vix_settlement_late_reversal_long`, signal type `vix_expiration_session`; enter long NQ at 15:00:00 ET next-bar open and flatten by 15:55 ET.

Entry module: `vix_expiration_pressure`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.
