# first_hour_1000_long

Mechanic: enter long after the completed first half-hour of RTH.

Entry timing: signal at the completed 10:00 ET 5-minute bar close, entry at the next bar open.

Stop logic: fixed `percent_from_entry` stop at `0.005`.

Take-profit / exit logic: fixed `fixed_r` target at `3.0R`; otherwise flatten at 15:55 ET.

Session rationale: waits for the opening auction and first-half-hour imbalance to settle before testing RTH drift.

Lookahead control: no unclosed bar or future session statistic is used.
