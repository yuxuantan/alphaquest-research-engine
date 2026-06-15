# open_two_sided_ibs_reversion

Mechanic: at the 09:35 ET completed 5-minute bar close, trade ES long after low prior-session IBS or short after high prior-session IBS.

This expresses the campaign edge as a symmetric two-sided prior-session mean-reversion rule.

Entry timing: the signal is evaluated only after the 09:30-09:34 bar is complete and enters on the 09:35 next-bar open.

Stop logic: `percent_from_entry`, tuned only through `sl.params.stop_pct`.

Take-profit / exit logic: `fixed_r`, tuned only through `tp.params.target_r_multiple`; otherwise flatten at 15:55 ET.

Session restrictions: RTH only, America/New_York timestamps, one trade per day, no overnight exposure.

Forced flatten: Apex rules require flat before the configured 16:58:30 ET force-flatten time; this variant's planned flatten is 15:55 ET.

Lookahead control: only completed prior RTH high/low/close and the completed 09:30-09:34 signal bar are available to the signal.
