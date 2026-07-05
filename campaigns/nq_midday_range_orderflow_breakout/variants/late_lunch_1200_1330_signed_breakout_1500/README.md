# late_lunch_1200_1330_signed_breakout_1500

Campaign: `nq_midday_range_orderflow_breakout`

Mechanic: completed 12:00-13:30 ET late-lunch range breakout with total signed-flow confirmation through 15:00 ET; enter on the next 5-minute bar open and flatten at 15:55 ET unless stop or target is hit.

Flow mode: `signed_volume`. NQ range cap grid `[80, 100, 120]` was selected from pre-PnL signal density, not returns.

Source ES config: `campaigns/es_midday_range_orderflow_breakout/variants/late_lunch_1200_1330_signed_breakout_1500/config.yaml`

Lookahead control: the midday range is frozen only after its window closes; breakout and orderflow confirmation use completed bars; fills are next-bar open or later.
