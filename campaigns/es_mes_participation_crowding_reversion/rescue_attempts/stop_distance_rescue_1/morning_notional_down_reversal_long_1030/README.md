# morning_notional_down_reversal_long_1030

Mechanic: use the completed 10:29 ET bar. If 30-minute MES notional-equivalent participation is high versus prior same-clock history and ES has fallen by the configured number of ticks, enter long ES at the next bar open and flatten by 12:00 ET.

Parameters: `share_rank_min`, `min_abs_return_ticks`, `stop_pct`, and `target_r_multiple`.

Lookahead control: MES participation rank uses only prior same-clock observations; ES return and MES share use completed bars only. No future high/low, final VWAP, final session return, or post-entry MES/ES data is used.


Rescue attempt 1: parameter-space-only rescue. Rescue broadens stop/target space around the original robust long-side top rows while keeping the same participation-crowding trigger.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_mes_participation_crowding_reversion/morning_notional_down_reversal_long_1030/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.
