# prior_session_late_hedge_unwind_long_1500

Campaign: `es_vix_expiration_pressure`

Mechanic: On the regular session before VIX settlement, enter long ES at 15:00 ET next bar open and flatten by 15:55 ET.

Entry module: `vix_expiration_pressure`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.
