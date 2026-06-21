# First 60-minute signed-flow continuation at 10:30

Edge expression: At the completed 10:30 ET minute, trade ES with the full first-hour RTH return only when completed aggregate signed-volume imbalance from 09:30-10:30 agrees with that return.

Expected profitability mechanism: A first-hour move that survives the initial opening rotation and is confirmed by broad aggressive flow should proxy persistent same-day demand or supply rather than a one-bar stop probe.

Timing and causality: the opening-window return and aggregate orderflow inputs are complete at 10:30:00 ET. The engine can only enter at the next bar open, applies configured ES commission, one-tick slippage, tick rounding, pessimistic same-bar stop/target handling, and forced flatten by 12:30:00 ET.

Failure modes: aggregate Sierra signed flow is a proxy, opening momentum may reverse after the source window, large-trade confirmation can mark exhaustion, and any positive result may be concentrated in specific volatility regimes.
