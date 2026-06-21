# afternoon_trade_up_reversal_short_1400

Mechanic: use the completed 13:59 ET bar. If 60-minute MES trade-count share is high versus prior same-clock history and ES has risen by the configured number of ticks, enter short ES at the next bar open and flatten by 15:55 ET.

Parameters: `share_rank_min`, `min_abs_return_ticks`, `stop_pct`, and `target_r_multiple`.

Lookahead control: MES trade-share rank uses only prior same-clock observations; ES return and MES trade share use completed bars only. No future high/low, final VWAP, final session return, or post-entry MES/ES data is used.


Rescue attempt 1: parameter-space-only rescue. Rescue tests nearby tighter short-side payoff/stop space and higher trade-share ranks; mechanic is unchanged.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_mes_participation_crowding_reversion/afternoon_trade_up_reversal_short_1400/rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.
