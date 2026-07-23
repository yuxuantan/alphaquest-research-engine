# morning_signed_two_sided_breakout_1030

Campaign: `es_overnight_range_compression_orderflow_breakout`

## Mechanics

Two-sided 5-minute RTH continuation after a compressed overnight range and a completed morning close outside the overnight high/low with same-direction signed aggregate flow.

- Entry: `overnight_range_orderflow_breakout`
- Stop: `sweep_extreme`
- Target: `fixed_r`
- Timeframe: `5m`
- Orderflow mode: `signed`

## Pre-Test Rationale

This expresses the edge as pent-up overnight range expansion through either known overnight boundary. The signal only uses the completed overnight range, completed RTH breakout close, and completed same-bar aggregate flow, then relies on next-bar execution.


## Rescue Attempt 1

Parameter-space rescue only. Entry, stop, target modules, data, costs, sessions, and core mechanic are unchanged. The rescue broadens the lower-to-middle overnight range rank and tests quicker fixed-R continuation targets before any second rescue is allowed.
