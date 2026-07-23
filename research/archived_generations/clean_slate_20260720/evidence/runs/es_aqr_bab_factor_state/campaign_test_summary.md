# ES AQR BAB Factor State Campaign Summary

Decision: FAIL.

All five original variants failed `limited_core_grid_test`. Each failed variant received exactly one parameter-space-only rescue. Four rescues also failed `limited_core_grid_test`.

The strongest rescue, `low_bab_z63_rebound_long_1100/rescue1`, passed limited core and limited monkey but failed `walk_forward_analysis`: early exit occurred on window 2 because selected in-sample PF was `0.99 < 1.00`. Stitched OOS PF was `0.8619637937819756` and MAR was `-0.3811286271107167`.

No run reached WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
