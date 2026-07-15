# first30_noncontinuation_1000

Mechanic: trade two-sided ES overnight gap reversals unless the completed first 30-minute RTH window strongly continues the overnight gap.

Entry timing: signal at the completed 09:55-10:00 ET 5-minute bar close after the 30-minute window is complete, entry at the next bar open.

Stop logic: `percent_from_entry` stop, tuned only through the predeclared grid.

Take-profit / exit logic: `fixed_r` target, tuned only through the predeclared grid; otherwise flatten at 15:55 ET.

Session rationale: tests whether avoiding strong opening continuation is enough to express the overnight reversal edge.

Lookahead control: uses only previous RTH close, current RTH open, and the completed first 30-minute confirmation window.
