# up_day_rebalance_long_1500

Campaign: `es_leveraged_etf_rebalance_pressure`

Mechanic: at 15:00 ET, enter long ES only after a sufficiently large positive completed same-day return from the prior RTH close. This isolates upside LETF rebalance demand.

Lookahead controls: prior RTH close is known before the session; the signal uses the completed 14:59-15:00 bar close; fills occur no earlier than next bar open; no final-session close, final high/low, final VWAP, or future return is used.
