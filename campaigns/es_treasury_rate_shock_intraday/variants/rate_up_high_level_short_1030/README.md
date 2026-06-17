# rate_up_high_level_short_1030

Campaign: `es_treasury_rate_shock_intraday`

Mechanic: At 10:30 ET, short ES when the latest strictly prior DGS10 change rank and DGS10 level rank are both high; flatten by 15:55.

Feature timing: Treasury observations are strictly earlier than the ES session date, and the 10:30 signal enters after the completed 10:29-10:30 bar.

Entry module: `treasury_rate_state` with setup mode `rate_up_high_level_short`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.
