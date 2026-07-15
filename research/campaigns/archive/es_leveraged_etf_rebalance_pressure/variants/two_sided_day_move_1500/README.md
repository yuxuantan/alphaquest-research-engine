# two_sided_day_move_1500

Campaign: `es_leveraged_etf_rebalance_pressure`

Mechanic: at 15:00 ET, trade ES in the direction of a sufficiently large completed same-day return from the prior RTH close. This expresses the same LETF rebalance-pressure edge closer to the closing rebalance window.

Lookahead controls: prior RTH close is known before the session; the signal uses the completed 14:59-15:00 bar close; fills occur no earlier than next bar open; no final-session close, final high/low, final VWAP, or future return is used.
