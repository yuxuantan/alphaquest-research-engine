# morning_signed_gap_hold_continuation_1030

Campaign: `es_opening_gap_orderflow_continuation`

## Mechanics
10:00-10:30 ET signed-flow continuation after a held opening gap.

The variant waits for a completed source window, requires the opening gap to remain unfilled relative to the prior RTH close, confirms same-direction `signed_imbalance` aggregate orderflow, enters no earlier than the next bar open, uses an opening-gap boundary stop around the prior close, and exits at fixed R or forced flatten.

## Modules
- Entry: `opening_gap_orderflow_continuation`
- Stop: `opening_gap_boundary`
- Target: `fixed_r`
