# open30_price_flow_divergence_fade_1400

This variant shorts after a completed first-30-minute upside price drive when the opening signed-flow imbalance is weak, then waits until 14:00 ET for same-day delta context. The signal is evaluated at the 13:59 close for intended next-bar execution at 14:00 ET and flattens at 14:30 ET.

Tunable parameters are fixed before testing: opening return threshold, opening volume-rank threshold, percent stop, and fixed-R target.

