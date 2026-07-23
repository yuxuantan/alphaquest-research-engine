# morning_mes_buy_pressure_reversion_short

Mechanic: at 10:00 ET, trade ES short when completed 09:30-09:59 MES-minus-ES signed-flow imbalance is above the configured threshold.

This expresses the campaign edge by treating strong MES buy pressure versus ES as temporary liquidity demand that may reverse in ES.

Entry timing: the signal is evaluated on the 09:59 bar close and enters on the 10:00 next-bar open.

Stop logic: `percent_from_entry`, tuned only through `sl.params.stop_pct`.

Take-profit / exit logic: `fixed_r`, tuned only through `tp.params.target_r_multiple`; otherwise flatten at 11:31 ET.

Session restrictions: RTH only, America/New_York timestamps, one trade per day.

Forced flatten: Apex rules require flat before the configured 16:59:59 ET close; this variant's planned flatten is 11:31 ET.

Lookahead control: only completed bars through 09:59 are available to the signal.
