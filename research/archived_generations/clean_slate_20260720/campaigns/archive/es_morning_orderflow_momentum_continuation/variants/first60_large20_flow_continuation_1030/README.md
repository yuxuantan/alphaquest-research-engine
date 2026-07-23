# First 60-minute large-20-flow continuation at 10:30

Edge expression: At the completed 10:30 ET minute, trade ES with the first-hour price move only when completed large-20 trade signed imbalance over 09:30-10:30 points in the same direction.

Expected profitability mechanism: Large aggressive prints aligned with the first-hour return can represent informed or urgent participation; the variant tests whether that pressure continues after next-bar execution despite ES costs.

Timing and causality: the opening-window return and aggregate orderflow inputs are complete at 10:30:00 ET. The engine can only enter at the next bar open, applies configured ES commission, one-tick slippage, tick rounding, pessimistic same-bar stop/target handling, and forced flatten by 12:30:00 ET.

Failure modes: aggregate Sierra signed flow is a proxy, opening momentum may reverse after the source window, large-trade confirmation can mark exhaustion, and any positive result may be concentrated in specific volatility regimes.
