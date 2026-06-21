# late_morning_large20_flow_continuation_1030

Mechanic: 10:30 ET continuation on all-available non-standard-monthly SPX 0DTE sessions using large20 trade imbalance from the completed 09:30-10:30 source window.

This variant expresses the SPX 0DTE orderflow-continuation edge by requiring a known 0DTE calendar session, a completed ES open-to-signal move, and completed aggregate orderflow aligned with that move. It enters only after the source window is closed and relies on the engine for next-bar-open execution.

Stop/target: `percent_from_entry` stop and `fixed_r` target, with same-day flatten at `15:55:00` ET.

Lookahead controls: no option volume, dealer gamma, final VWAP, future high/low, future orderflow, or post-signal path information is used. Standard monthly OPEX sessions are excluded by default to avoid overlapping the active monthly/quarterly OPEX families.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_spx_0dte_orderflow_continuation/late_morning_large20_flow_continuation_1030/run1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.
