# high_overnight_first15_short_1000

Mechanic: short ES after large positive overnight gaps only when the completed first 15-minute RTH window confirms reversal downward.

Entry timing: signal at the completed 09:55-10:00 ET 5-minute bar close after the 15-minute window is complete, entry at the next bar open.

Stop logic: `percent_from_entry` stop, tuned only through the predeclared grid.

Take-profit / exit logic: `fixed_r` target, tuned only through the predeclared grid; otherwise flatten at 15:55 ET.

Session rationale: isolates the short side of the overnight-intraday reversal effect without adding post-result filters.

Lookahead control: uses only previous RTH close, current RTH open, and the completed first 15-minute confirmation window.
