# santa_momentum_confirmed_midday_long_1200

Edge: NQ turn-of-year seasonal effect.

Mechanic: At 12:00 ET during the turn-of-year window, buy NQ only when completed same-session return from the first RTH open clears the predeclared threshold.

Rationale: Momentum-confirmed expression tests whether the calendar edge needs same-day confirmation while still using only completed bars before entry.

Timing: the signal is evaluated only after a completed one-minute RTH bar at 12:00:00 America/New_York time, with next-bar/open-boundary execution and mandatory 15:55 ET flatten.

Parameter space: 3+ values are declared in `config.yaml`; total official combinations = 27.
