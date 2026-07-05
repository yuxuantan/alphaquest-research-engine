# january_first2_open_long_1000

Edge: NQ turn-of-year seasonal effect.

Mechanic: At 10:00 ET during only the first two regular January sessions, buy NQ on the next bar boundary and flatten same day.

Rationale: January-only expression tests the narrow turn-of-year component most directly associated with January-effect literature.

Timing: the signal is evaluated only after a completed one-minute RTH bar at 10:00:00 America/New_York time, with next-bar/open-boundary execution and mandatory 15:55 ET flatten.

Parameter space: 3+ values are declared in `config.yaml`; total official combinations = 9.
