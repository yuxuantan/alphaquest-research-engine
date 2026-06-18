# Morning Support Sell Absorption Long

Trades a completed 5-minute reclaim of a fixed 25-point ES round-number support
barrier only when aggregate signed flow on the signal bar is negative. The
variant expresses absorption: aggressive selling fails to keep price below a
known barrier, then entry waits for the next bar open with a fixed percent stop,
fixed-R target, and forced intraday flatten.
