# Midday low-VR large-trade exhaustion reversion through 14:30

Edge expression: From 11:00 through 14:30 ET, fade completed 15-minute ES moves in low variance-ratio states when large-10 signed flow presses into a move that does not close near the bar extreme.

Expected profitability mechanism: Midday low-serial-dependence states should favor liquidity-provision reversals, and large-trade pressure into a weak close location is a completed-bar proxy for exhausted pressure.

Timing and causality: all variance-ratio, return, close-location, and aggregate-orderflow inputs are computed after the signal bar is complete. The engine enters at the next bar open or later and applies configured ES costs, slippage, tick rounding, same-bar pessimistic stop/target ordering, and forced flatten.

Failure modes: the variance-ratio estimate can be unstable, aggregate signed flow is only a completed-bar proxy, the average move may be too small after ES costs, and stress tests may reveal dependency on narrow volatility regimes.


## Rescue Attempt 1

Original top row favored the lowest VR threshold with large-trade pressure and wider stop/target; rescue focuses on more clearly anti-persistent midday states while keeping the same reversion mechanic. Entry module, stop module, target module, data, costs, sessions, and validation gates are unchanged.
