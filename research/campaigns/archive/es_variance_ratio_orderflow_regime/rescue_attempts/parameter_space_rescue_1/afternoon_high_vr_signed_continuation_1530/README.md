# Afternoon high-VR signed-flow continuation through 15:30

Edge expression: From 13:00 through 15:30 ET, trade with a completed 15-minute move when a two-hour, 30-minute-horizon variance ratio indicates persistent afternoon structure and aggregate signed flow confirms.

Expected profitability mechanism: If afternoon portfolio and hedging flows create persistent intraday paths, high variance-ratio confirmation should identify the sessions where late continuation is more likely than mean reversion.

Timing and causality: all variance-ratio, return, close-location, and aggregate-orderflow inputs are computed after the signal bar is complete. The engine enters at the next bar open or later and applies configured ES costs, slippage, tick rounding, same-bar pessimistic stop/target ordering, and forced flatten.

Failure modes: the variance-ratio estimate can be unstable, aggregate signed flow is only a completed-bar proxy, the average move may be too small after ES costs, and stress tests may reveal dependency on narrow volatility regimes.


## Rescue Attempt 1

Original top row preferred high VR, stronger flow, wider stop, and larger target; rescue narrows toward that same afternoon persistence expression without adding filters. Entry module, stop module, target module, data, costs, sessions, and validation gates are unchanged.
