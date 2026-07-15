# afternoon_mes_large20_buy_pressure_short

Mechanic: at 14:00 ET, trade ES short when completed 13:55-13:59 MES large-20 buy imbalance is strong while ES five-minute return is capped.

This expresses the campaign edge by fading smaller-notional aggressive buy pressure that ES has not confirmed.

Entry timing: the signal is evaluated on the 13:59 bar close and enters on the 14:00 next-bar open.

Stop logic: `percent_from_entry`, tuned only through `sl.params.stop_pct`.

Take-profit / exit logic: `fixed_r`, tuned only through `tp.params.target_r_multiple`; otherwise flatten at 15:31 ET.

Session restrictions: RTH only, America/New_York timestamps, one trade per day.

Forced flatten: Apex rules require flat before the configured 16:59:59 ET close; this variant's planned flatten is 15:31 ET.

Lookahead control: only completed bars through 13:59 are available to the signal.
