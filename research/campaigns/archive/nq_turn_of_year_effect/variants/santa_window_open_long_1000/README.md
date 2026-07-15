# santa_window_open_long_1000

Edge: NQ turn-of-year seasonal effect.

Mechanic: At 10:00 ET during the last-five-December plus first-two-January turn-of-year window, buy NQ on the next bar boundary and flatten same day.

Rationale: Opening-hour long expression of the turn-of-year equity-index futures seasonal window.

Timing: the signal is evaluated only after a completed one-minute RTH bar at 10:00:00 America/New_York time, with next-bar/open-boundary execution and mandatory 15:55 ET flatten.

Parameter space: 3+ values are declared in `config.yaml`; total official combinations = 9.
