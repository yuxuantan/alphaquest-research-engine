# two_sided_spread_change_large10_1130

Two-sided NQ continuation based on lagged default-spread change. Tightening plus NQ/large-10 buying allows longs, while widening plus NQ/large-10 selling allows shorts by 10:00, 10:30, or 11:30 ET.


## Rescue 1

Parameter-space-only rescue after all five original variants failed. This rescue keeps the same default-spread/orderflow mechanic and does not change TP because every target_r_multiple is already >= 1.0R. It changes only adjacent credit threshold, orderflow threshold, and stop-distance values.


NQ port note: ported from the ES parameter-space rescue source before any NQ PnL inspection; NQ rescues are not authorized.
