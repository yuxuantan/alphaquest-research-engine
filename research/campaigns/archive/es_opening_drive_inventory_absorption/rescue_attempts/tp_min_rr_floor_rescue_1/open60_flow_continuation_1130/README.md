# open60_flow_continuation_1130

This variant goes short after a completed first-60-minute RTH opening drive when downside price return, signed trade imbalance, cumulative delta, and volume-rank context remain aligned. The signal is evaluated at the 11:29 close for intended next-bar execution at 11:30 ET and flattens at 13:30 ET.

Tunable parameters are fixed before testing: opening return threshold, opening volume-rank threshold, percent stop, and fixed-R target.



## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_opening_drive_inventory_absorption/open60_flow_continuation_1130/rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.
