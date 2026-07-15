# lunch_1130_1300_large10_breakout_1430

Campaign: `nq_midday_range_orderflow_breakout`

Mechanic: completed 11:30-13:00 ET lunch range breakout with large-10 signed-flow confirmation through 14:30 ET; enter on the next 5-minute bar open and flatten at 15:55 ET unless stop or target is hit.

Flow mode: `large10`. NQ range cap grid `[80, 100, 120]` was selected from pre-PnL signal density, not returns.

Source ES config: `campaigns/es_midday_range_orderflow_breakout/variants/lunch_1130_1300_large10_breakout_1430/config.yaml`

Lookahead control: the midday range is frozen only after its window closes; breakout and orderflow confirmation use completed bars; fills are next-bar open or later.
