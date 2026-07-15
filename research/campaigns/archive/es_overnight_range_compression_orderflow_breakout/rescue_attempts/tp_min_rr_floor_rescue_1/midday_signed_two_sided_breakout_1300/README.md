# midday_signed_two_sided_breakout_1300

Campaign: `es_overnight_range_compression_orderflow_breakout`

## Mechanics

Two-sided 5-minute midday continuation from compressed overnight high/low boundaries, confirmed by signed aggregate flow.

- Entry: `overnight_range_orderflow_breakout`
- Stop: `sweep_extreme`
- Target: `fixed_r`
- Timeframe: `5m`
- Orderflow mode: `signed`

## Pre-Test Rationale

This variant tests whether compressed overnight levels remain valid beyond the open. It keeps the same completed-bar breakout and aggregate-flow confirmation but avoids adding any post-result filters.


## Rescue Attempt 1

Parameter-space rescue only. Entry, stop, target modules, data, costs, sessions, and core mechanic are unchanged. The rescue broadens the lower-to-middle overnight range rank and tests quicker fixed-R continuation targets before any second rescue is allowed.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_overnight_range_compression_orderflow_breakout/midday_signed_two_sided_breakout_1300/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_overnight_range_compression_orderflow_breakout/midday_signed_two_sided_breakout_1300/stop_widen_rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.
