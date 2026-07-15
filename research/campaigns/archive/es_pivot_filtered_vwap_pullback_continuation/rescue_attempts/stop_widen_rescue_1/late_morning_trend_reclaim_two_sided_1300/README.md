# late_morning_trend_reclaim_two_sided_1300 stop_widen_rescue_1

Parameter-only rescue for `late_morning_trend_reclaim_two_sided_1300` after the original staged validation failed. Entry mechanics, signal window, VWAP setup mode, carried pivot filter, data windows, costs, and target grid are unchanged. The stop grid changes from `[0.0015, 0.0025, 0.004]` to `[0.0025, 0.004, 0.006]`, and the fixed-config stop changes from `0.0025` to `0.004`.

This is the only allowed rescue for this failed variant. Target R values remain `[1.0, 1.5]`; no target is below 1.0R.
