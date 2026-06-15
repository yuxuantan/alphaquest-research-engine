# midday_mes_price_richness_fade

Mechanic: at 11:00 ET, fade completed 10:57-10:59 MES-minus-ES return richness in ES.

This expresses the campaign edge by treating a short linked-contract price dislocation as temporary rather than durable ES information.

Entry timing: the signal is evaluated on the 10:59 bar close and enters on the 11:00 next-bar open.

Stop logic: `percent_from_entry`, tuned only through `sl.params.stop_pct`.

Take-profit / exit logic: `fixed_r`, tuned only through `tp.params.target_r_multiple`; otherwise flatten at 14:30 ET.

Session restrictions: RTH only, America/New_York timestamps, one trade per day.

Forced flatten: Apex rules require flat before the configured 16:59:59 ET close; this variant's planned flatten is 14:30 ET.

Lookahead control: only completed bars through 10:59 are available to the signal.
