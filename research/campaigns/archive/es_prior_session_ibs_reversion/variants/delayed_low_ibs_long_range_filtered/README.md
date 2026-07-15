# delayed_low_ibs_long_range_filtered

Mechanic: at the 10:00 ET completed 5-minute bar close, go long ES after low prior-session IBS when the prior RTH range is within the predeclared range filter.

This expresses the campaign edge as a delayed low-IBS long entry that avoids the opening print and excludes unusually wide prior sessions.

Entry timing: the signal is evaluated only after the 09:55-09:59 bar is complete and enters on the 10:00 next-bar open.

Stop logic: `percent_from_entry`, tuned only through `sl.params.stop_pct`.

Take-profit / exit logic: `fixed_r`, tuned only through `tp.params.target_r_multiple`; otherwise flatten at 15:55 ET.

Session restrictions: RTH only, America/New_York timestamps, one trade per day, no overnight exposure.

Forced flatten: Apex rules require flat before the configured 16:58:30 ET force-flatten time; this variant's planned flatten is 15:55 ET.

Lookahead control: only completed prior RTH high/low/close and the completed 09:55-09:59 signal bar are available to the signal.
