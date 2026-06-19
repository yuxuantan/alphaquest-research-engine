# afternoon_large20_two_sided_breakout_1500

Campaign: `es_overnight_range_compression_orderflow_breakout`

## Mechanics

Two-sided 5-minute afternoon continuation from compressed overnight high/low boundaries, confirmed by large20 aggregate flow and flattened before the end of RTH.

- Entry: `overnight_range_orderflow_breakout`
- Stop: `sweep_extreme`
- Target: `fixed_r`
- Timeframe: `5m`
- Orderflow mode: `large20`

## Pre-Test Rationale

This is the most selective orderflow expression of the campaign. It asks whether large-trade participation can confirm late-session expansion away from a compressed overnight range without relying on overnight exposure.
