# prior_session_late_hedge_unwind_long_1500

Campaign: `nq_vix_expiration_pressure`

Mechanic: setup_mode `prior_session_late_hedge_unwind_long`, signal type `previous_regular_session`; enter long NQ at 15:00:00 ET next-bar open and flatten by 15:55 ET.

Entry module: `vix_expiration_pressure`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.
