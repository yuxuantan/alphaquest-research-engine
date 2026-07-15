# Midday high-VR large-trade continuation through 14:00

Edge expression: From 11:00 through 14:00 ET, trade with a completed 15-minute move only when the prior two hours show high variance-ratio persistence and large-10 trade flow agrees with price direction.

Expected profitability mechanism: Midday continuation is only credible when the path is statistically persistent and larger trade buckets participate, which should reduce false continuation signals in choppy lunch trading.

Timing and causality: all variance-ratio, return, close-location, and aggregate-orderflow inputs are computed after the signal bar is complete. The engine enters at the next bar open or later and applies configured NQ costs, slippage, tick rounding, same-bar pessimistic stop/target ordering, and forced flatten.

Failure modes: the variance-ratio estimate can be unstable, aggregate signed flow is only a completed-bar proxy, the average move may be too small after NQ costs, and stress tests may reveal dependency on narrow volatility regimes.
