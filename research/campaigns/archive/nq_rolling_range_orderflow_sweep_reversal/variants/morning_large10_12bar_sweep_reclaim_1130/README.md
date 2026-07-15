# morning_large10_12bar_sweep_reclaim_1130

Mechanic: From 09:45 through 11:30 ET, fade the first completed rolling high/low sweep and reclaim only when large10 aggregate flow indicates pressure into the failed sweep.

Rationale: ported from the ES rolling-range sweep-reclaim campaign before NQ PnL inspection; uses completed NQ 5-minute bars and aggregate orderflow absorption.
