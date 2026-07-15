# Morning high-VR signed-flow continuation through 11:30

Edge expression: From 09:50 through 11:30 ET, trade with a completed 15-minute ES move only when the preceding 90-minute rolling variance ratio is above one and same-window aggregate signed flow agrees with the move.

Expected profitability mechanism: If high variance ratio marks serially persistent price action, then a completed morning move with aligned aggregate flow should have continuation pressure before lunch rather than immediate reversal.

Timing and causality: all variance-ratio, return, close-location, and aggregate-orderflow inputs are computed after the signal bar is complete. The engine enters at the next bar open or later and applies configured ES costs, slippage, tick rounding, same-bar pessimistic stop/target ordering, and forced flatten.

Failure modes: the variance-ratio estimate can be unstable, aggregate signed flow is only a completed-bar proxy, the average move may be too small after ES costs, and stress tests may reveal dependency on narrow volatility regimes.
