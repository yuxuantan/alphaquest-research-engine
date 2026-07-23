# or15_full_session_large10_trend_reclaim_1530

OR15 full-session large10-flow trend reclaim.

Mechanic: Build the first 15-minute RTH opening range. From range completion through 15:30 ET, require a completed close outside the range and a reclaim back inside within eight bars. Enter in the reclaim direction only when the pre-breakout 3-bar and 6-bar trend windows agree and same-direction large10 signed-volume imbalance confirms the reclaim.

Why this should be profitable: the public opening range can attract breakout traders; when a completed break fails and reclaims back inside the range in the same direction as the pre-breakout 3-bar and 6-bar trend structure, same-direction completed aggregate orderflow may indicate that the trapped side is being absorbed and price can continue away from the failed break. The test uses next-bar execution, configured ES costs, and no future-derived levels.

Failure modes: full-session opening-range levels may decay, the loosened trend filter may admit chop, orderflow confirmation may be noisy, and costs/slippage may overwhelm the rotation.

## Rescue 1

Parameter-space/fixed-parameter rescue only. The opening-range failed-breakout reclaim, frozen pre-breakout trend context, and completed orderflow confirmation are unchanged. The rescue widens the allowed reclaim timing and tests smaller fixed-R targets to see whether the same trap-reclaim mechanic was over-constrained in the original grid.
