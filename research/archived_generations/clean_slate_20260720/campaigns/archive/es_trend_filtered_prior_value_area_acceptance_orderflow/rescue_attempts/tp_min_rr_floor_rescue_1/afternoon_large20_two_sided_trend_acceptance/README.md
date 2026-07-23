# afternoon_large20_two_sided_trend_acceptance

Two-sided ES prior-value-area acceptance variant. It trades 12:30-15:30 ET when a completed 5-minute bar accepts beyond prior VAH or VAL, large20 signed-volume imbalance confirms direction, and completed trend windows agree. Entry is next bar open; stop is percent from entry; target is fixed-R; unresolved trades flatten at 15:55 ET.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_trend_filtered_prior_value_area_acceptance_orderflow/afternoon_large20_two_sided_trend_acceptance/run1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.
