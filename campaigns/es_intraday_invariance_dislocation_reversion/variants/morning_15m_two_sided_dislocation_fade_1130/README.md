# Morning 15m Two-Sided Dislocation Fade

Mechanic: From 09:50 through 11:30 ET, fade either direction of a completed 15-minute move when the intraday trading-invariance dislocation score is high versus prior same-clock observations and aggregate signed flow is not strongly aligned with the move.

Why it should be profitable: The morning version should work only if early-session price dislocations without signed-flow sponsorship are temporary liquidity transfers rather than durable information.

The signal uses completed one-minute ES bars only, ranks the current invariance-dislocation score against prior same-clock observations, enters no earlier than the next bar open, uses a fixed percent stop, uses fixed-R targets no lower than 1.0R, and flattens before the configured cutoff.
