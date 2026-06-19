# afternoon_5m_large20_24bar_reversion_1500 Rescue 1

Campaign: `es_rolling_stat_envelope_orderflow_reversion`

This is the one allowed parameter-space/fixed-parameter rescue for `afternoon_5m_large20_24bar_reversion_1500`.

The core mechanic is unchanged: completed close outside a prior-completed rolling statistical envelope, same-side aggregate orderflow pressure into the extreme, next-bar entry, signal-bar-extreme stop, and fixed-R target.

Changes are limited to stricter `band_z`, stricter `min_orderflow_imbalance`, a larger fixed `min_bar_range_ticks`, and wider stop/target parameter space.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_rolling_stat_envelope_orderflow_reversion/afternoon_5m_large20_24bar_reversion_1500/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.
