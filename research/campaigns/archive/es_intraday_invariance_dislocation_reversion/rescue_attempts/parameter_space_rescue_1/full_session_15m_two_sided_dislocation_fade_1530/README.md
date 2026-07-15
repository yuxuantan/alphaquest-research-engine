# Full-Session 15m Two-Sided Dislocation Fade

Mechanic: From 10:00 through 15:30 ET, fade completed 15-minute high-invariance-dislocation moves in either direction when aggregate signed flow is not strongly aligned with the move.

Why it should be profitable: The broad session variant tests whether the invariance dislocation mechanism is not confined to one clock window: high price movement per transaction without signed-flow sponsorship should tend to retrace across RTH.

The signal uses completed one-minute ES bars only, ranks the current invariance-dislocation score against prior same-clock observations, enters no earlier than the next bar open, uses a fixed percent stop, uses fixed-R targets no lower than 1.0R, and flattens before the configured cutoff.

Rescue note: parameter-space-only rescue 1 keeps the same mechanic and tests less sparse high-dislocation thresholds, a wider fixed percent stop neighborhood, and fixed-R targets no lower than 1.0R.
