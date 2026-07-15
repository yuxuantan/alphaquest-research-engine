# midmorning_1030_long

Mechanic: enter long after the completed 10:25-10:30 ET bar.

Entry timing: signal at the completed 10:30 ET 5-minute bar close, entry at the next bar open.

Stop logic: fixed `percent_from_entry` stop at `0.005`.

Take-profit / exit logic: fixed `fixed_r` target at `3.0R`; otherwise flatten at 15:55 ET.

Session rationale: tests whether any RTH premium is more reliable after the first hour of cash-session information is visible.

Lookahead control: the entry does not inspect future highs, lows, VWAP, or session return.
