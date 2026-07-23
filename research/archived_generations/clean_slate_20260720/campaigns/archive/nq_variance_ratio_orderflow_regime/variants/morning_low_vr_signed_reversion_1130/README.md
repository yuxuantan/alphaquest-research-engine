# Morning low-VR signed-flow exhaustion reversion through 11:30

Edge expression: From 09:50 through 11:30 ET, fade a completed 15-minute move when the rolling variance ratio is below one, aggregate signed flow is pushing in the move direction, and the signal bar does not close at the extreme.

Expected profitability mechanism: Low variance ratio implies anti-persistent/choppy price action; if aggressive flow pushes into a move that fails to close near the extreme, the next tradeable leg should more often retrace.

Timing and causality: all variance-ratio, return, close-location, and aggregate-orderflow inputs are computed after the signal bar is complete. The engine enters at the next bar open or later and applies configured NQ costs, slippage, tick rounding, same-bar pessimistic stop/target ordering, and forced flatten.

Failure modes: the variance-ratio estimate can be unstable, aggregate signed flow is only a completed-bar proxy, the average move may be too small after NQ costs, and stress tests may reveal dependency on narrow volatility regimes.
