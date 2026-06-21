# od30_notional_failed_extension_reversal_1300

30-minute opening drive, notional MES participation crowding, failed extension monitored through 13:00 ET.

This variant belongs to `es_opening_drive_mes_crowding_reversal`. It uses only the existing local ES/MES completed-bar Sierra participation cache. No paid data is required or downloaded.

Entry mechanics are fixed before PnL testing: freeze the first `30` minutes of RTH, require a later completed failed extension beyond the opening-drive extreme, require elevated MES `notional` participation rank on that completed failure bar, and enter ES on the next bar open. Stops use the failed-extension sweep extreme plus a declared tick offset; targets are fixed-R and all positions are flattened by `14:00:00` ET.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_opening_drive_mes_crowding_reversal/od30_notional_failed_extension_reversal_1300/run1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.
