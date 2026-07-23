# morning_15m_fragmented_up_fade_short

Mechanic: at 10:00, 10:30, and 11:00 ET, short ES after a completed 15-minute
up move when same-clock trade-count rank is high and same-clock average-trade
size rank is low. It enters on the next 1-minute bar open and uses per-slot
flatten times ending no later than 11:20 ET.

This expresses the campaign edge as morning fragmented-liquidity reversion
after short-window upward pressure.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_trade_fragmentation_liquidity_reversion/morning_15m_fragmented_up_fade_short/run1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.
