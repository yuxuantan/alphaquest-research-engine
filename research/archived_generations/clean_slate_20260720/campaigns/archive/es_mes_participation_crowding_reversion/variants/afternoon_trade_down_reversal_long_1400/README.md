# afternoon_trade_down_reversal_long_1400

Mechanic: use the completed 13:59 ET bar. If 60-minute MES trade-count share is high versus prior same-clock history and ES has fallen by the configured number of ticks, enter long ES at the next bar open and flatten by 15:55 ET.

Parameters: `share_rank_min`, `min_abs_return_ticks`, `stop_pct`, and `target_r_multiple`.

Lookahead control: MES trade-share rank uses only prior same-clock observations; ES return and MES trade share use completed bars only. No future high/low, final VWAP, final session return, or post-entry MES/ES data is used.
