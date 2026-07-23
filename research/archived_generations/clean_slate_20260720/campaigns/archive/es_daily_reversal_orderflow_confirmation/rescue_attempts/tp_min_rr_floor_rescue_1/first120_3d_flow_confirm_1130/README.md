# first120_3d_flow_confirm_1130

This variant tests ES daily short-term reversal only when completed aggregate orderflow confirms the reversal direction. At 11:30:00 ET it fades the prior 3-session completed RTH close-to-close return if the first completed 120 minutes of RTH flow has signed-volume imbalance in the contrarian direction. The signal is generated on the completed 5-minute bar and can enter only on the next bar open.

Stop is percent-from-entry, target is fixed R, and all positions flatten by 15:55 ET.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_daily_reversal_orderflow_confirmation/first120_3d_flow_confirm_1130/run1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.
