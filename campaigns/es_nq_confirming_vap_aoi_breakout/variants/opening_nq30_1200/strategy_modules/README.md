# opening_nq30_1200 strategy modules

Entry module: `nq_confirming_vap_aoi_breakout` with completed-bar ES breakout, ES signed-flow confirmation, and completed rolling NQ return/signed-imbalance confirmation.

Stop-loss module: `sweep_extreme`, placing the stop beyond the completed breakout bar extreme plus the configured tick offset.

Take-profit module: `cost_adjusted_fixed_r`, using only entry, stop distance, configured ES tick value, commission, and slippage.

Mechanic: Isolates morning opening-range continuation after the first 30 completed RTH minutes, using NQ confirmation only after the range is known.
