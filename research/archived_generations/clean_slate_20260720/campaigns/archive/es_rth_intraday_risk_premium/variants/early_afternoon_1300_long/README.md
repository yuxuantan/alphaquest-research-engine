# early_afternoon_1300_long

Mechanic: enter long after the completed 12:55-13:00 ET bar.

Entry timing: signal at the completed 13:00 ET 5-minute bar close, entry at the next bar open.

Stop logic: fixed `percent_from_entry` stop at `0.005`.

Take-profit / exit logic: fixed `fixed_r` target at `3.0R`; otherwise flatten at 15:55 ET.

Session rationale: tests whether any RTH long premium is concentrated after the lunch lull rather than the morning.

Lookahead control: no future bar or final session statistic is used.
