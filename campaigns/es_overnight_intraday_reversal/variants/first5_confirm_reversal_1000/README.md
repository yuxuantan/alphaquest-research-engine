# first5_confirm_reversal_1000

Mechanic: trade two-sided ES overnight gap reversals when the completed first 5-minute RTH bar confirms against the overnight gap.

Entry timing: signal at the completed 09:55-10:00 ET 5-minute bar close, entry at the next bar open.

Stop logic: `percent_from_entry` stop, tuned only through the predeclared grid.

Take-profit / exit logic: `fixed_r` target, tuned only through the predeclared grid; otherwise flatten at 15:55 ET.

Session rationale: gives the opening 5-minute liquidity shock time to show reversal, then waits until 10:00 ET before entering.

Lookahead control: uses only previous RTH close, current RTH open, and the completed first 5-minute confirmation window.
