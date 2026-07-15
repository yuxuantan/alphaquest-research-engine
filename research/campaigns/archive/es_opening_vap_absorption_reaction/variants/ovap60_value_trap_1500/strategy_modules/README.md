# ovap60_value_trap_1500 strategy modules

Entry module: `opening_vap_absorption_reaction` with setup mode `opening60_value_trap_two_sided`.

Stop-loss module: `sweep_extreme`, placing the stop beyond the completed signal bar extreme plus the configured tick offset.

Take-profit module: `cost_adjusted_fixed_r`, using only entry, stop distance, configured ES tick value, commission, and slippage.

Mechanic: Range model using the first 60 completed RTH minutes, requiring failed auction extension at opening value-area high or low plus adverse signed flow and footprint absorption.
