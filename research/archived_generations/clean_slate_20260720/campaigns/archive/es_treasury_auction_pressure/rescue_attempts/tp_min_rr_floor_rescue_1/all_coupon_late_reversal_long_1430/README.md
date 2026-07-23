# all_coupon_late_reversal_long_1430

Campaign: `es_treasury_auction_pressure`

Mechanic: On previously announced nominal Treasury Note/Bond auction days, go long ES after the completed 14:29-14:30 ET bar and flatten by 15:55. This tests late-day absorption/recovery after auction supply pressure.

Entry module: `treasury_auction_pressure`. It reads the locked local calendar `data/external/es_treasury_coupon_auction_sessions_20110103_20260609.csv`, requires the configured auction scope, waits for the configured completed 1-minute bar close, and relies on the engine for next-bar-open execution.

Stop module: `percent_from_entry` with declared stop grid.

Target module: `fixed_r` with declared R-multiple grid.

Parameter grid: `sl.params.stop_pct` x `tp.params.target_r_multiple` = 9 combinations. Entry scope, time, and direction are fixed mechanics for this variant.

Lookahead controls: no auction outcome, high yield, bid-to-cover, dealer award, total accepted, final ES high/low, final VWAP, or future Treasury/ES data is used. Auction rows require `announcemt_date < auction_date`.

## Rescue Attempt 1

This is the single allowed rescue for this failed variant. It keeps the same core mechanic, entry module, stop module, target module, auction scope, signal time, direction, data, execution costs, sessions, and validation gates. Only the stop/target parameter space changes to `sl.params.stop_pct` = [0.001, 0.0015, 0.0025] and `tp.params.target_r_multiple` = [0.5, 0.75, 1.0].


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_treasury_auction_pressure/all_coupon_late_reversal_long_1430/rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.
