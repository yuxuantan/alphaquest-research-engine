# midday_signed_24bar_sweep_reclaim_1400

Mechanic: From 11:00 through 14:00 ET, fade completed sweeps of the prior rolling intraday range when total signed flow is absorbed and price closes back inside the range.

Rationale: ported from the ES rolling-range sweep-reclaim campaign before NQ PnL inspection; uses completed NQ 5-minute bars and aggregate orderflow absorption.
