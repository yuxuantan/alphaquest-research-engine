# id_nr4_prior_session_breakout

Mechanic: after a completed prior RTH inside day that also ranks as the narrowest range in the last four sessions, trade a two-sided breakout of the prior RTH high or low.

Entry timing: the signal is evaluated on a completed 5-minute bar close and enters on the next 5-minute bar open.

Stop logic: `percent_from_entry`, tuned only through `sl.params.stop_pct`.

Take-profit / exit logic: `fixed_r`, tuned only through `tp.params.target_r_multiple`; otherwise flatten at 15:55 ET.

Session restrictions: RTH only, America/New_York timestamps, one trade per day, no overnight exposure.

Lookahead control: the inside-day and range-compression conditions use only completed prior RTH sessions.
