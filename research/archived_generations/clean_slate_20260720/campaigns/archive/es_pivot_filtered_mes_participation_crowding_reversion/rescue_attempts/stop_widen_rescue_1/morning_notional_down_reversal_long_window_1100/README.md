# morning_notional_down_reversal_long_window_1100 stop_widen_rescue_1

Parameter-only rescue for `morning_notional_down_reversal_long_window_1100` after original staged validation failed. Entry mechanics, signal window, carried pivot filter, data windows, costs, and target grid are unchanged. The stop grid changes from `[0.0015, 0.0025, 0.004]` to `[0.0025, 0.004, 0.006]`, and the fixed-config stop changes from `0.0025` to `0.004`.

This is the only allowed rescue for this failed variant. Target R values remain `[1.0, 1.5, 2.0]`; no target is below 1.0R.
