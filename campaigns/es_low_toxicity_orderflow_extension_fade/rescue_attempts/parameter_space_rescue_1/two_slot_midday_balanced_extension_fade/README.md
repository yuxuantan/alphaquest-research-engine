# two_slot_midday_balanced_extension_fade

Two midday slots fade low-toxicity extensions: 12:30 down-extension long and 13:30 up-extension short. The variant uses completed 5-minute bars, same-clock rank63 orderflow-state filters, next-bar entry, fixed-R target, and same-day flatten.


## parameter_space_rescue_1

The one allowed rescue keeps the slot definitions, entry module, TP grid, data, costs, fills, sessions, and validation gates unchanged. It only tightens the low-toxicity rank grid to `[0.25, 0.35, 0.45]`, raises the completed-extension grid to `[4, 5, 6]` ticks, and widens the stop grid to `[0.004, 0.006, 0.008]`.
