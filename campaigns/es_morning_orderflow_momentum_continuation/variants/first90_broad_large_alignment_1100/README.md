# First 90-minute broad and large-flow alignment at 11:00

Edge expression: At the completed 11:00 ET minute, trade ES with the 09:30-11:00 RTH price move only when both broad signed-volume imbalance and large-20 signed imbalance agree with the move.

Expected profitability mechanism: Requiring both broad and large-trade flow alignment after the first 90 minutes should reject weaker one-sided noise while keeping enough trades to test persistent intraday pressure.

Timing and causality: the opening-window return and aggregate orderflow inputs are complete at 11:00:00 ET. The engine can only enter at the next bar open, applies configured ES commission, one-tick slippage, tick rounding, pessimistic same-bar stop/target handling, and forced flatten by 14:00:00 ET.

Failure modes: aggregate Sierra signed flow is a proxy, opening momentum may reverse after the source window, large-trade confirmation can mark exhaustion, and any positive result may be concentrated in specific volatility regimes.
