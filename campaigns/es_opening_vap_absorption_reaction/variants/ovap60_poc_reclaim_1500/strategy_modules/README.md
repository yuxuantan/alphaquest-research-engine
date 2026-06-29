# ovap60_poc_reclaim_1500 strategy modules

Entry module: `opening_vap_absorption_reaction` with setup mode `opening60_poc_reclaim_two_sided`.

Stop-loss module: `sweep_extreme`, placing the stop beyond the completed signal bar extreme plus the configured tick offset.

Take-profit module: `cost_adjusted_fixed_r`, using only entry, stop distance, configured ES tick value, commission, and slippage.

Mechanic: Range/magnet model using the first 60 completed RTH minutes, trading only POC reclaim with adverse signed flow and footprint absorption as trapped-trader evidence.
