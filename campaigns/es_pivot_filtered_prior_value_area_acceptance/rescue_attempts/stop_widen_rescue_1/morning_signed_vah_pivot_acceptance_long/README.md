# morning_signed_vah_pivot_acceptance_long stop_widen_rescue_1

Parameter-only rescue for `morning_signed_vah_pivot_acceptance_long` after original staged validation failed. Entry mechanics, value-area approximation, orderflow confirmation, signal window, carried pivot filter, data windows, costs, and target grid are unchanged. The stop grid changes from `[0.002, 0.003, 0.0045]` to `[0.003, 0.0045, 0.006]`, and the fixed-config stop changes from `0.003` to `0.0045`.

This is the only allowed rescue for this failed variant. Target R values remain `[1.0, 1.5]`; no target is below 1.0R.
