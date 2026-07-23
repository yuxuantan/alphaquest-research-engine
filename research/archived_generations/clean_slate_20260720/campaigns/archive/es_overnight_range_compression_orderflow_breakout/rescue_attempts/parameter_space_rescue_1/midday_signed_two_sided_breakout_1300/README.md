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
