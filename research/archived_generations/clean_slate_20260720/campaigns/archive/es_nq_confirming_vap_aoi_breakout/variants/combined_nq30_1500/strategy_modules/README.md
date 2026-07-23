# combined_nq30_1500 strategy modules

Entry module: `nq_confirming_vap_aoi_breakout` with completed-bar ES breakout, ES signed-flow confirmation, and completed rolling NQ return/signed-imbalance confirmation.

Stop-loss module: `sweep_extreme`, placing the stop beyond the completed breakout bar extreme plus the configured tick offset.

Take-profit module: `cost_adjusted_fixed_r`, using only entry, stop distance, configured ES tick value, commission, and slippage.

Mechanic: Uses prior RTH plus opening-range AOIs with a 30-minute ES/NQ confirmation window as the central cross-index continuation expression.
