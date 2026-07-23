# Lunch 15m Two-Sided Dislocation Fade

Mechanic: From 12:00 through 13:30 ET, fade completed 15-minute high-dislocation moves when the same-clock invariance rank is elevated and aggregate signed flow is not strongly aligned.

Why it should be profitable: Lunch-period liquidity can be shallow; a high movement-per-transaction score without flow sponsorship should be a plausible temporary dislocation rather than a trend signal.

The signal uses completed one-minute ES bars only, ranks the current invariance-dislocation score against prior same-clock observations, enters no earlier than the next bar open, uses a fixed percent stop, uses fixed-R targets no lower than 1.0R, and flattens before the configured cutoff.
