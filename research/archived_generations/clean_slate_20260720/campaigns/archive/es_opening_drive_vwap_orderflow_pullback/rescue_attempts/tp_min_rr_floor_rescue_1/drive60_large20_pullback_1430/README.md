# drive60_large20_pullback_1430

60-minute opening-drive bias, large-20-lot aggregate-flow VWAP pullback/reclaim through 14:30 ET.

Entry: `vwap_orderflow_pullback_continuation` in `opening_drive_pullback` mode. Stop: `sweep_extreme`. Target: `fixed_r`.

The variant starts state collection at 09:30 ET so the opening-drive window is known before any VWAP pullback/reclaim signal can fire.


Rescue 1: parameter-space-only rescue. It keeps the same opening-drive VWAP pullback/reclaim and aggregate-orderflow mechanic while changing only declared parameter values and the fixed VWAP pullback tolerance.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_opening_drive_vwap_orderflow_pullback/drive60_large20_pullback_1430/rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.
