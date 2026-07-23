# Midday 15m Two-Sided Dislocation Fade

Mechanic: From 11:00 through 14:00 ET, fade either direction of a completed 15-minute move when the invariance dislocation score is high versus prior same-clock observations and signed flow does not strongly sponsor the move.

Why it should be profitable: Midday liquidity is often thinner; an unusually large price move per transaction without matching signed-flow sponsorship should be more likely to retrace than continue.

The signal uses completed one-minute ES bars only, ranks the current invariance-dislocation score against prior same-clock observations, enters no earlier than the next bar open, uses a fixed percent stop, uses fixed-R targets no lower than 1.0R, and flattens before the configured cutoff.

Rescue note: parameter-space-only rescue 1 keeps the same mechanic and tests less sparse high-dislocation thresholds, a wider fixed percent stop neighborhood, and fixed-R targets no lower than 1.0R.
