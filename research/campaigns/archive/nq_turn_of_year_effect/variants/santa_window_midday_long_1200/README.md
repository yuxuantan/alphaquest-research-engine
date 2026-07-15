# santa_window_midday_long_1200

Edge: NQ turn-of-year seasonal effect.

Mechanic: At 12:00 ET during the full turn-of-year window, buy NQ on the next bar boundary and flatten same day.

Rationale: Midday expression tests whether the seasonal bid persists after the opening auction and early volatility.

Timing: the signal is evaluated only after a completed one-minute RTH bar at 12:00:00 America/New_York time, with next-bar/open-boundary execution and mandatory 15:55 ET flatten.

Parameter space: 3+ values are declared in `config.yaml`; total official combinations = 9.
