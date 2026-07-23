# od60_notional_failed_extension_reversal_1530

60-minute opening drive, notional MES participation crowding, failed extension monitored through 15:30 ET.

This variant belongs to `es_opening_drive_mes_crowding_reversal`. It uses only the existing local ES/MES completed-bar Sierra participation cache. No paid data is required or downloaded.

Entry mechanics are fixed before PnL testing: freeze the first `60` minutes of RTH, require a later completed failed extension beyond the opening-drive extreme, require elevated MES `notional` participation rank on that completed failure bar, and enter ES on the next bar open. Stops use the failed-extension sweep extreme plus a declared tick offset; targets are fixed-R and all positions are flattened by `15:55:00` ET.
