# late_morning_1100_long

Mechanic: enter long after the completed 10:55-11:00 ET bar.

Entry timing: signal at the completed 11:00 ET 5-minute bar close, entry at the next bar open.

Stop logic: fixed `percent_from_entry` stop at `0.005`.

Take-profit / exit logic: fixed `fixed_r` target at `3.0R`; otherwise flatten at 15:55 ET.

Session rationale: tests a late-morning entry after the highest opening volatility has usually passed.

Lookahead control: no future bar or final session statistic is used.
