# drive30_large10_pullback_1230

30-minute opening-drive bias, large-10-lot aggregate-flow VWAP pullback/reclaim through 12:30 ET.

Entry: `vwap_orderflow_pullback_continuation` in `opening_drive_pullback` mode. Stop: `sweep_extreme`. Target: `fixed_r`.

The variant starts state collection at 09:30 ET so the opening-drive window is known before any VWAP pullback/reclaim signal can fire.


Rescue 1: parameter-space-only rescue. It keeps the same opening-drive VWAP pullback/reclaim and aggregate-orderflow mechanic while changing only declared parameter values and the fixed VWAP pullback tolerance.
