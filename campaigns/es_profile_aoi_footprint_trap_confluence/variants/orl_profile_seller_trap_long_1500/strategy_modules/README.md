# Strategy Modules

Entry: `profile_aoi_footprint_trap`

Stop-loss: `sweep_extreme`

Take-profit / exit: `cost_adjusted_fixed_r` plus forced flatten at `15:55:00` ET.

Mechanic: Trade only seller traps below ORL when ORL is near a prior profile level and the completed footprint bar shows sell imbalance absorbed below the close.
