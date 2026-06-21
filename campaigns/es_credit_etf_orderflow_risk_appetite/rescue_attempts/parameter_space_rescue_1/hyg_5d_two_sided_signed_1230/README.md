# hyg_5d_two_sided_signed_1230

Trade ES in the direction of same-session price/flow when five-day HYG return rank is in either tail.


## Rescue 1

Parameter-space-only rescue after all original variants failed. It keeps the same HYG credit-ETF/orderflow mechanic and does not change TP because every target_r_multiple is already >= 1.0R. It changes only adjacent HYG rank threshold, signed-flow threshold, and stop-distance values.
