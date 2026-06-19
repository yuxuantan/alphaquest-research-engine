# late_morning_large10_two_sided_breakout_1130

Campaign: `es_overnight_range_compression_orderflow_breakout`

## Mechanics

Two-sided 5-minute late-morning continuation from compressed overnight high/low boundaries, confirmed by aligned large-trade aggregate flow.

- Entry: `overnight_range_orderflow_breakout`
- Stop: `sweep_extreme`
- Target: `fixed_r`
- Timeframe: `5m`
- Orderflow mode: `large10`

## Pre-Test Rationale

The late-morning window allows the market to digest the open while still testing continuation away from a compressed overnight range. Large-trade flow is used as the confirmation proxy to reduce noise from small prints.


## Rescue Attempt 1

Parameter-space rescue only. Entry, stop, target modules, data, costs, sessions, and core mechanic are unchanged. The rescue broadens the lower-to-middle overnight range rank and tests quicker fixed-R continuation targets before any second rescue is allowed.
