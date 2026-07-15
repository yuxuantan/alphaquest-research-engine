# Midday high-VR large-trade continuation through 14:00

Edge expression: From 11:00 through 14:00 ET, trade with a completed 15-minute move only when the prior two hours show high variance-ratio persistence and large-10 trade flow agrees with price direction.

Expected profitability mechanism: Midday continuation is only credible when the path is statistically persistent and larger trade buckets participate, which should reduce false continuation signals in choppy lunch trading.

Timing and causality: all variance-ratio, return, close-location, and aggregate-orderflow inputs are computed after the signal bar is complete. The engine enters at the next bar open or later and applies configured ES costs, slippage, tick rounding, same-bar pessimistic stop/target ordering, and forced flatten.

Failure modes: the variance-ratio estimate can be unstable, aggregate signed flow is only a completed-bar proxy, the average move may be too small after ES costs, and stress tests may reveal dependency on narrow volatility regimes.


## Rescue Attempt 1

Original top rows favored the strictest VR and large-trade-flow corner with wider stops; rescue focuses the same continuation mechanic on stronger persistent moves and larger-flow confirmation. Entry module, stop module, target module, data, costs, sessions, and validation gates are unchanged.
