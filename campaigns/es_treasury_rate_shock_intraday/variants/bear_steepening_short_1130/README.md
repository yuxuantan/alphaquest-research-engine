# bear_steepening_short_1130

Campaign: `es_treasury_rate_shock_intraday`

Mechanic: At 11:30 ET, short ES when the latest strictly prior DGS10 change rank and 10y-2y curve-change rank are both high; flatten by 15:55.

Feature timing: Treasury observations are strictly earlier than the ES session date, and the 11:30 signal enters after the completed 11:29-11:30 bar.

Entry module: `treasury_rate_state` with setup mode `bear_steepening_short`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.
