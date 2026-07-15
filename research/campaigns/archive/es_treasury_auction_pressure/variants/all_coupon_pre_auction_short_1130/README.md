# all_coupon_pre_auction_short_1130

Campaign: `es_treasury_auction_pressure`

Mechanic: On previously announced nominal Treasury Note/Bond auction days, short ES after the completed 11:29-11:30 ET bar and flatten by 15:55. This expresses pre-result auction supply/risk-capacity pressure before the usual 13:00 coupon auction result window.

Entry module: `treasury_auction_pressure`. It reads the locked local calendar `data/external/es_treasury_coupon_auction_sessions_20110103_20260609.csv`, requires the configured auction scope, waits for the configured completed 1-minute bar close, and relies on the engine for next-bar-open execution.

Stop module: `percent_from_entry` with declared stop grid.

Target module: `fixed_r` with declared R-multiple grid.

Parameter grid: `sl.params.stop_pct` x `tp.params.target_r_multiple` = 9 combinations. Entry scope, time, and direction are fixed mechanics for this variant.

Lookahead controls: no auction outcome, high yield, bid-to-cover, dealer award, total accepted, final ES high/low, final VWAP, or future Treasury/ES data is used. Auction rows require `announcemt_date < auction_date`.
