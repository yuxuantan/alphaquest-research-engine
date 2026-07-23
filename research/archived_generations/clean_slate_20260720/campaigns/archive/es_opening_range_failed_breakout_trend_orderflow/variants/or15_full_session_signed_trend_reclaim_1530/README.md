# or15_full_session_signed_trend_reclaim_1530

OR15 full-session signed-flow trend reclaim.

Mechanic: Build the first 15-minute RTH opening range. From range completion through 15:30 ET, require a completed close outside the range and a reclaim back inside within eight bars. Enter in the reclaim direction only when the pre-breakout 3-bar and 6-bar trend windows agree and same-direction signed-volume imbalance confirms the reclaim.

Why this should be profitable: the public opening range can attract breakout traders; when a completed break fails and reclaims back inside the range in the same direction as the pre-breakout 3-bar and 6-bar trend structure, same-direction completed aggregate orderflow may indicate that the trapped side is being absorbed and price can continue away from the failed break. The test uses next-bar execution, configured ES costs, and no future-derived levels.

Failure modes: full-session opening-range levels may decay, the loosened trend filter may admit chop, orderflow confirmation may be noisy, and costs/slippage may overwhelm the rotation.
