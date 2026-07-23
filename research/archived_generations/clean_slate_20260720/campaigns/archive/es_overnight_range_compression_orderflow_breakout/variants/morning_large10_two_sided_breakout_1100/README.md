# morning_large10_two_sided_breakout_1100

Campaign: `es_overnight_range_compression_orderflow_breakout`

## Mechanics

Two-sided 5-minute RTH continuation after a compressed overnight range and a completed morning close outside the overnight high/low with same-direction large10 aggregate flow.

- Entry: `overnight_range_orderflow_breakout`
- Stop: `sweep_extreme`
- Target: `fixed_r`
- Timeframe: `5m`
- Orderflow mode: `large10`

## Pre-Test Rationale

This variant tests whether larger-trade participation confirms the same morning compression-breakout edge in either direction. It remains a completed-bar signal with next-bar execution and no post-result filters.
