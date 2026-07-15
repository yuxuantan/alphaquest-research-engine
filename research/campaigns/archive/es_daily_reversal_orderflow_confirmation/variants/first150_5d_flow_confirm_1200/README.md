# first150_5d_flow_confirm_1200

This variant tests ES daily short-term reversal only when completed aggregate orderflow confirms the reversal direction. At 12:00:00 ET it fades the prior 5-session completed RTH close-to-close return if the first completed 150 minutes of RTH flow has signed-volume imbalance in the contrarian direction. The signal is generated on the completed 5-minute bar and can enter only on the next bar open.

Stop is percent-from-entry, target is fixed R, and all positions flatten by 15:55 ET.
