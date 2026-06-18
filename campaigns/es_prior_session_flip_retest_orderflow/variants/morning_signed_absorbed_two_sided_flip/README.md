# morning_signed_absorbed_two_sided_flip

Campaign: `es_prior_session_flip_retest_orderflow`

## Mechanics
Morning two-sided prior-level break, retest, and hold; counter-pressure in total signed flow must be absorbed at the retest.

The variant records a completed break beyond the prior RTH high or low, waits for a later completed retest that holds on the breakout side, confirms the retest with `absorbed` `signed` aggregate flow, enters no earlier than the next bar open, places the stop beyond the flipped prior level, and exits at fixed R or forced flatten. Prior-level freshness is deliberately disabled because the S/R flip thesis can remain valid after earlier probes of the same public level.

## Modules
- Entry: `pdh_pdl_orderflow_breakout_continuation`
- Stop: `prior_level_retest_boundary`
- Target: `fixed_r`
