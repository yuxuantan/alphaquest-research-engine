# First 30-minute signed-flow continuation at 10:00

Edge expression: At the completed 10:00 ET minute, trade ES in the direction of the 09:30-10:00 RTH price move only when aggregate signed-volume imbalance over that same completed opening window has the same sign.

Expected profitability mechanism: A directional first half-hour with matching aggressive signed flow can indicate order-splitting and unresolved price pressure; entering on the next minute tests whether that pressure persists after the opening window.

Timing and causality: the opening-window return and aggregate orderflow inputs are complete at 10:00:00 ET. The engine can only enter at the next bar open, applies configured ES commission, one-tick slippage, tick rounding, pessimistic same-bar stop/target handling, and forced flatten by 11:30:00 ET.

Failure modes: aggregate Sierra signed flow is a proxy, opening momentum may reverse after the source window, large-trade confirmation can mark exhaustion, and any positive result may be concentrated in specific volatility regimes.
