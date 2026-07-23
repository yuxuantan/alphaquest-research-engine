# morning_low_delta_divergence_long

Morning long fade when ES makes a fresh RTH low but cumulative signed-volume progress since the prior low is weak.

Mechanic: From 10:00 through 12:00 ET, use only completed RTH bars. If the signal bar makes a fresh session low by at least the grid threshold, closes no more than 8 ticks below the prior completed session low, and cumulative signed-volume progress since that prior low is not sufficiently negative, enter long at the next 1-minute open. Flatten by 15:55 ET unless the stop or target is hit.

Stop: percent-from-entry stop, rounded to ES tick size.

Target: fixed-R target.

Lookahead control: the prior high/low reference is from bars completed before the signal bar; the signal bar is used only after close; entry is next bar open.
