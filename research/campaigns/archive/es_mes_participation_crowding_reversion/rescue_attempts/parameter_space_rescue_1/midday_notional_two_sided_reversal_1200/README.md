# midday_notional_two_sided_reversal_1200

Mechanic: use the completed 11:59 ET bar. If 60-minute MES notional-equivalent participation is high versus prior same-clock history and ES has moved far enough, fade the completed ES move at the next bar open and flatten by 14:00 ET.

Parameters: `share_rank_min`, `min_abs_return_ticks`, `stop_pct`, and `target_r_multiple`.

Lookahead control: MES participation rank uses only prior same-clock observations; ES return and MES share use completed bars only. No future high/low, final VWAP, final session return, or post-entry MES/ES data is used.


Rescue attempt 1: parameter-space-only rescue. Rescue shifts to stronger participation/return extremes and neighboring wider stop/target values; two-sided fade mechanic is unchanged.
