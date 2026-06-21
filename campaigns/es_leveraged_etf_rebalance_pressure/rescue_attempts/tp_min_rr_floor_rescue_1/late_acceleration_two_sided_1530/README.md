# late_acceleration_two_sided_1530

Campaign: `es_leveraged_etf_rebalance_pressure`

Mechanic: at 15:30 ET, trade ES in the direction of a large completed same-day return only when the completed 15:00-15:30 ET return is also moving in the same direction. This keeps the same LETF rebalance-pressure edge and adds a predeclared late-window acceleration expression.

Lookahead controls: prior RTH close is known before the session; the signal uses only bars completed by 15:30 ET; fills occur no earlier than next bar open; no final-session close, final high/low, final VWAP, or future return is used.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_leveraged_etf_rebalance_pressure/late_acceleration_two_sided_1530/rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.
