# first15_confirm_reversal_1000

Mechanic: trade two-sided ES overnight gap reversals when the completed first 15-minute RTH window confirms against the overnight gap.

Entry timing: signal at the completed 09:55-10:00 ET 5-minute bar close after the 15-minute window is complete, entry at the next bar open.

Stop logic: `percent_from_entry` stop, tuned only through the predeclared grid.

Take-profit / exit logic: `fixed_r` target, tuned only through the predeclared grid; otherwise flatten at 15:55 ET.

Session rationale: requires more opening evidence than the 5-minute variant while still entering before late-morning drift dominates.

Lookahead control: uses only previous RTH close, current RTH open, and the completed first 15-minute confirmation window.
