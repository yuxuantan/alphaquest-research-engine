# First 45-minute large-trade-flow continuation at 10:15

Edge expression: At the completed 10:15 ET minute, trade ES with the 09:30-10:15 RTH price move only when large-10 trade signed imbalance over the same completed window supports the move.

Expected profitability mechanism: If larger aggressive trades represent slower institutional execution, a 45-minute opening move confirmed by large-trade imbalance should be more likely to continue before liquidity fully mean-reverts.

Timing and causality: the opening-window return and aggregate orderflow inputs are complete at 10:15:00 ET. The engine can only enter at the next bar open, applies configured ES commission, one-tick slippage, tick rounding, pessimistic same-bar stop/target handling, and forced flatten by 12:00:00 ET.

Failure modes: aggregate Sierra signed flow is a proxy, opening momentum may reverse after the source window, large-trade confirmation can mark exhaustion, and any positive result may be concentrated in specific volatility regimes.
