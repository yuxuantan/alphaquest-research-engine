# open_0935_long

Mechanic: enter long NQ after the completed 09:30-09:35 ET RTH bar.

Entry timing: signal at the completed 09:35:00 ET 5-minute bar close, entry at the next bar open or later.

Stop logic: fixed `percent_from_entry` stop at `0.005`.

Take-profit / exit logic: fixed `fixed_r` target at `3.0R`; otherwise flatten at 15:55 ET.

Session rationale: tests whether broad RTH drift begins immediately after the opening bar without using the unclosed open bar.

Lookahead control: no current-session high/low/VWAP/final return is used; weekday, signal time, and the completed signal bar are available before entry.
