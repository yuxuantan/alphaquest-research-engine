# three_slot_up_extension_fade_short

Three short-only slots fade upside extensions when same-clock orderflow imbalance is unusually low. The variant uses completed 5-minute bars, same-clock rank63 orderflow-state filters, next-bar entry, fixed-R target, and same-day flatten.


## parameter_space_rescue_1

The one allowed rescue keeps the slot definitions, entry module, TP grid, data, costs, fills, sessions, and validation gates unchanged. It only tightens the low-toxicity rank grid to `[0.25, 0.35, 0.45]`, raises the completed-extension grid to `[4, 5, 6]` ticks, and widens the stop grid to `[0.004, 0.006, 0.008]`.
