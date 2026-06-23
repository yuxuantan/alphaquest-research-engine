# late_morning_large10_gap_absorption_fade_1100

Campaign: `nq_opening_gap_orderflow_absorption_fade`

Entry module: `opening_gap_orderflow_fade`. Stop module: `percent_from_entry`. Target module: `gap_fill_fraction`.

Mechanic: NQ opening-gap fade after completed 10:45:00 to 11:00:00 ET counter-gap large10 aggregate flow confirmation.

Parameter grid: `entry.params.min_opening_gap_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.fill_fraction` = 81 combinations.

Pre-PnL density note: late-morning large10 counter-gap broad/strict corners range about 49-92 signals/year for gap thresholds 20-60.
