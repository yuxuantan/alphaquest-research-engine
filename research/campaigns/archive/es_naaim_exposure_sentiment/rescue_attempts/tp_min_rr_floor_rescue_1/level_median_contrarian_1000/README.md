# level_median_contrarian_1000 rescue1

Parameter-space-only rescue for the failed original variant. It preserves the NAAIM active-manager exposure mechanic, setup mode, entry time, two-business-day data availability rule, data window, costs, and validation gates. Only the same stop/target modules are retested with stop_pct=[0.00075, 0.001, 0.00125] and target_r_multiple=[0.5, 0.75, 1.0].


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_naaim_exposure_sentiment/level_median_contrarian_1000/rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.
