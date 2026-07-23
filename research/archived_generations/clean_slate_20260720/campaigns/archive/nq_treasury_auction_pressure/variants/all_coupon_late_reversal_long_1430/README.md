# all_coupon_late_reversal_long_1430

Campaign: `nq_treasury_auction_pressure`

Mechanic: On previously announced nominal Treasury Note/Bond auction days, go long NQ after the completed 14:29-14:30 ET bar and flatten by 15:55. This tests late-day absorption/recovery after auction supply pressure.

Entry module: `treasury_auction_pressure`. It reads the locked local calendar `data/external/nq_treasury_coupon_auction_sessions_20110103_20260612.csv`, requires the configured auction scope, waits for the configured completed 1-minute bar close, and relies on the engine for next-bar-open execution.

Stop module: `percent_from_entry` with declared stop grid.

Target module: `fixed_r` with declared R-multiple grid.

Parameter grid: `sl.params.stop_pct` x `tp.params.target_r_multiple` = 9 combinations. Entry scope, time, and direction are fixed mechanics for this variant.

Lookahead controls: no auction outcome, high yield, bid-to-cover, dealer award, total accepted, final NQ high/low, final VWAP, or future Treasury/NQ data is used. Auction rows require `announcemt_date < auction_date`.
