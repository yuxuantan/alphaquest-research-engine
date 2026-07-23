# two_sided_day_move_1430

Campaign: `es_leveraged_etf_rebalance_pressure`

Mechanic: at 14:30 ET, trade ES in the direction of a sufficiently large completed same-day return from the prior RTH close. This is a pre-close LETF rebalance-pressure proxy, not first-half-hour market intraday momentum.

Lookahead controls: prior RTH close is known before the session; the signal uses the completed 14:29-14:30 bar close; fills occur no earlier than next bar open; no final-session close, final high/low, final VWAP, or future return is used.
