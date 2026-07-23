# Afternoon 15m Two-Sided Dislocation Fade

Mechanic: From 13:00 through 15:30 ET, fade completed 15-minute dislocation moves when the invariance score is high relative to prior same-clock history and aggregate signed flow is not strongly aligned.

Why it should be profitable: Afternoon liquidity demand can push ES inefficiently; when price movement per transaction is abnormal and signed flow fails to confirm sponsorship, the completed move should have reversion pressure before the flat cutoff.

The signal uses completed one-minute ES bars only, ranks the current invariance-dislocation score against prior same-clock observations, enters no earlier than the next bar open, uses a fixed percent stop, uses fixed-R targets no lower than 1.0R, and flattens before the configured cutoff.

Rescue note: parameter-space-only rescue 1 keeps the same mechanic and tests less sparse high-dislocation thresholds, a wider fixed percent stop neighborhood, and fixed-R targets no lower than 1.0R.
