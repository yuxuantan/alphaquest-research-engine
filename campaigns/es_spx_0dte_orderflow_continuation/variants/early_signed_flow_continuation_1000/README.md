# early_signed_flow_continuation_1000

Mechanic: 10:00 ET continuation on all-available non-standard-monthly SPX 0DTE sessions using total signed-volume imbalance from the completed 09:30-10:00 source window.

This variant expresses the SPX 0DTE orderflow-continuation edge by requiring a known 0DTE calendar session, a completed ES open-to-signal move, and completed aggregate orderflow aligned with that move. It enters only after the source window is closed and relies on the engine for next-bar-open execution.

Stop/target: `percent_from_entry` stop and `fixed_r` target, with same-day flatten at `15:55:00` ET.

Lookahead controls: no option volume, dealer gamma, final VWAP, future high/low, future orderflow, or post-signal path information is used. Standard monthly OPEX sessions are excluded by default to avoid overlapping the active monthly/quarterly OPEX families.
