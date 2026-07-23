# all_day_1m_signed_30bar_reversion_1530 Rescue 1

Campaign: `es_rolling_stat_envelope_orderflow_reversion`

This is the one allowed parameter-space/fixed-parameter rescue for `all_day_1m_signed_30bar_reversion_1530`.

The core mechanic is unchanged: completed close outside a prior-completed rolling statistical envelope, same-side aggregate orderflow pressure into the extreme, next-bar entry, signal-bar-extreme stop, and fixed-R target.

Changes are limited to stricter `band_z`, stricter `min_orderflow_imbalance`, a larger fixed `min_bar_range_ticks`, and wider stop/target parameter space.
