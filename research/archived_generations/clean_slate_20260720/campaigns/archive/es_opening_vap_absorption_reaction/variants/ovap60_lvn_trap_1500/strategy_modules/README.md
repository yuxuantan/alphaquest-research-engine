# ovap60_lvn_trap_1500 strategy modules

Entry module: `opening_vap_absorption_reaction` with setup mode `opening60_lvn_trap_two_sided`.

Stop-loss module: `sweep_extreme`, placing the stop beyond the completed signal bar extreme plus the configured tick offset.

Take-profit module: `cost_adjusted_fixed_r`, using only entry, stop distance, configured ES tick value, commission, and slippage.

Mechanic: Low-volume-node reaction model using completed 60-minute opening LVNs, requiring adverse delta and footprint absorption to indicate trapped counterparty pressure.
