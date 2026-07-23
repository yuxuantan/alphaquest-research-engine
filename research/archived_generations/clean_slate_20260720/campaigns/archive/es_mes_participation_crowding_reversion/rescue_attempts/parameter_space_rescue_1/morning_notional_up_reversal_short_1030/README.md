# morning_notional_up_reversal_short_1030

Mechanic: use the completed 10:29 ET bar. If 30-minute MES notional-equivalent participation is high versus prior same-clock history and ES has risen by the configured number of ticks, enter short ES at the next bar open and flatten by 12:00 ET.

Parameters: `share_rank_min`, `min_abs_return_ticks`, `stop_pct`, and `target_r_multiple`.

Lookahead control: MES participation rank uses only prior same-clock observations; ES return and MES share use completed bars only. No future high/low, final VWAP, final session return, or post-entry MES/ES data is used.


Rescue attempt 1: parameter-space-only rescue. Rescue tests nearby tighter short-side payoff/stop space and higher participation ranks; trigger remains high MES participation plus completed ES up-move fade.
