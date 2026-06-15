# nr7_opening_range_30_breakout

Mechanic: after a completed prior RTH session ranks as the narrowest range in the last seven sessions, trade a two-sided breakout of the completed first 30-minute opening range.

Entry timing: the opening range is complete at 10:00 ET; signals use completed 5-minute bar closes and enter on the next 5-minute bar open.

Stop logic: `percent_from_entry`, tuned only through `sl.params.stop_pct`.

Take-profit / exit logic: `fixed_r`, tuned only through `tp.params.target_r_multiple`; otherwise flatten at 15:55 ET.

Session restrictions: RTH only, America/New_York timestamps, one trade per day, no overnight exposure.

Lookahead control: the opening range is not available until its configured window is complete.
