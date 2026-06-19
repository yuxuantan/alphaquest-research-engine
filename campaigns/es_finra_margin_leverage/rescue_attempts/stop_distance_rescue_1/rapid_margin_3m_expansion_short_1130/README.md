# rapid_margin_3m_expansion_short_1130 rescue1

This is the single allowed rescue attempt for `rapid_margin_3m_expansion_short_1130`.

Allowed change: the configured data-subset start date is moved to `2013-06-04`, the first ES session where this variant's frozen FINRA 120-month rank feature is non-null. The original limited-core slice began before the signal feature existed and generated zero trades.

No mechanics changed: same FINRA feature family, setup mode, signal direction, entry time, stop module, target module, flatten rule, execution assumptions, and parameter grid.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_finra_margin_leverage/rapid_margin_3m_expansion_short_1130/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.
