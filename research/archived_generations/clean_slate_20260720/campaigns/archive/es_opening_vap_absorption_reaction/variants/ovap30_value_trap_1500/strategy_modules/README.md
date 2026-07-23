# ovap30_value_trap_1500 strategy modules

Entry module: `opening_vap_absorption_reaction` with setup mode `opening30_value_trap_two_sided`.

Stop-loss module: `sweep_extreme`, placing the stop beyond the completed signal bar extreme plus the configured tick offset.

Take-profit module: `cost_adjusted_fixed_r`, using only entry, stop distance, configured ES tick value, commission, and slippage.

Mechanic: Range model: after the first 30 completed RTH minutes, fade failed moves through opening value-area edges when adverse delta and footprint absorption show trapped buyers or sellers.
