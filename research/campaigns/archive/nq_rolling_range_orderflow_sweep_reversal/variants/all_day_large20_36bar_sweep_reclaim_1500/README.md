# all_day_large20_36bar_sweep_reclaim_1500

Mechanic: From 09:45 through 15:00 ET, fade completed rolling-range sweeps only when the large20 bucket shows pressure into the failed break, using a broader lookback to define more meaningful intraday extremes.

Rationale: ported from the ES rolling-range sweep-reclaim campaign before NQ PnL inspection; uses completed NQ 5-minute bars and aggregate orderflow absorption.
