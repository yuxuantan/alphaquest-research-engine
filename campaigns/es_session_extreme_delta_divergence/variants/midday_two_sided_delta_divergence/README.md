# midday_two_sided_delta_divergence

Midday two-sided fade of fresh RTH highs or lows when cumulative signed-volume progress fails to confirm the new extreme.

Mechanic: From 11:00 through 14:00 ET, use only completed RTH bars after at least 60 one-minute bars have formed. Short a fresh session high or buy a fresh session low when the break exceeds the grid threshold, the close remains within 8 ticks of the prior completed extreme, and cumulative signed-volume progress from that prior extreme is weak in the breakout direction. Entry is next bar open; flatten is 15:55 ET.

Stop: percent-from-entry stop, rounded to ES tick size.

Target: fixed-R target.

Lookahead control: the prior high/low reference is from bars completed before the signal bar; the signal bar is used only after close; entry is next bar open.
