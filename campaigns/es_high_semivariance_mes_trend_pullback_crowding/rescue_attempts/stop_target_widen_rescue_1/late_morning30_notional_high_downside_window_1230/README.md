# late_morning30_notional_high_downside_window_1230 stop_target_widen_rescue_1

One allowed parameter-only rescue for `late_morning30_notional_high_downside_window_1230` after the original staged run failed. Entry mechanics, signal window, MES participation feature, prior ES trend-pullback condition, lagged high-semivariance filter, data windows, costs, session rules, and validation gates are unchanged.

The fixed-config stop changes from `0.003` to `0.004`; the stop grid changes from `[0.002, 0.003, 0.004]` to `[0.004, 0.006, 0.008]`; the target grid changes from `[1.0, 1.5, 2.0]` to `[1.5, 2.0, 2.5]`. No target reward:risk is below `1.0`.
