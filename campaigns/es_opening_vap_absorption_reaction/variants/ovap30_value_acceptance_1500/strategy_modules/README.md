# ovap30_value_acceptance_1500 strategy modules

Entry module: `opening_vap_absorption_reaction` with setup mode `opening30_value_acceptance_two_sided`.

Stop-loss module: `sweep_extreme`, placing the stop beyond the completed signal bar extreme plus the configured tick offset.

Take-profit module: `cost_adjusted_fixed_r`, using only entry, stop distance, configured ES tick value, commission, and slippage.

Mechanic: Trend/acceptance model: after the completed 30-minute opening profile, continue through VAH or VAL only when same-direction signed flow and footprint imbalance confirm acceptance.
