# december_window_long_1500

Edge: NQ turn-of-year seasonal effect.

Mechanic: At 15:00 ET during only the last five regular December sessions, buy NQ on the next bar boundary and flatten by 15:55 ET.

Rationale: Late-day December-only expression isolates potential year-end positioning or holiday-adjacent risk demand before the new year.

Timing: the signal is evaluated only after a completed one-minute RTH bar at 15:00:00 America/New_York time, with next-bar/open-boundary execution and mandatory 15:55 ET flatten.

Parameter space: 3+ values are declared in `config.yaml`; total official combinations = 6.
