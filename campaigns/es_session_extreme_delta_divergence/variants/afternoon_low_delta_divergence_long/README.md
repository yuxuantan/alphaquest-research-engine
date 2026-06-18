# afternoon_low_delta_divergence_long

Afternoon long fade when late-session ES pushes to a fresh low without cumulative signed-volume confirmation.

Mechanic: From 13:00 through 15:15 ET, buy a completed-bar fresh session low when the low clears the prior completed session low by the grid threshold, the close is still within 16 ticks of that prior low, and cumulative signed-volume progress since the prior low is not sufficiently negative. Entry waits for the next 1-minute open and flatten is 15:55 ET.

Stop: percent-from-entry stop, rounded to ES tick size.

Target: fixed-R target.

Lookahead control: the prior high/low reference is from bars completed before the signal bar; the signal bar is used only after close; entry is next bar open.
