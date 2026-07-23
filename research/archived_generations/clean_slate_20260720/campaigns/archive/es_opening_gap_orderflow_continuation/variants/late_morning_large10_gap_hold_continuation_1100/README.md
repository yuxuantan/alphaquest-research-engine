# late_morning_large10_gap_hold_continuation_1100

Campaign: `es_opening_gap_orderflow_continuation`

## Mechanics
10:45-11:00 ET large10-flow continuation after a held opening gap.

The variant waits for a completed source window, requires the opening gap to remain unfilled relative to the prior RTH close, confirms same-direction `large10_imbalance` aggregate orderflow, enters no earlier than the next bar open, uses an opening-gap boundary stop around the prior close, and exits at fixed R or forced flatten.

## Modules
- Entry: `opening_gap_orderflow_continuation`
- Stop: `opening_gap_boundary`
- Target: `fixed_r`
