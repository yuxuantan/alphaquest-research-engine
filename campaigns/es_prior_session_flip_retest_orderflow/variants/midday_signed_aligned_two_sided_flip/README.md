# midday_signed_aligned_two_sided_flip

Campaign: `es_prior_session_flip_retest_orderflow`

## Mechanics
Midday two-sided prior-level flip retest; total signed flow must align with the held retest direction.

The variant records a completed break beyond the prior RTH high or low, waits for a later completed retest that holds on the breakout side, confirms the retest with `aligned` `signed` aggregate flow, enters no earlier than the next bar open, places the stop beyond the flipped prior level, and exits at fixed R or forced flatten. Prior-level freshness is deliberately disabled because the S/R flip thesis can remain valid after earlier probes of the same public level.

## Modules
- Entry: `pdh_pdl_orderflow_breakout_continuation`
- Stop: `prior_level_retest_boundary`
- Target: `fixed_r`
