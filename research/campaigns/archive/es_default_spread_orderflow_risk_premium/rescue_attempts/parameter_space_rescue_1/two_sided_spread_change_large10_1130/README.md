# two_sided_spread_change_large10_1130

Two-sided ES continuation based on lagged default-spread change. Tightening plus ES/large-10 buying allows longs, while widening plus ES/large-10 selling allows shorts by 10:00, 10:30, or 11:30 ET.


## Rescue 1

Parameter-space-only rescue after all five original variants failed. This rescue keeps the same default-spread/orderflow mechanic and does not change TP because every target_r_multiple is already >= 1.0R. It changes only adjacent credit threshold, orderflow threshold, and stop-distance values.
