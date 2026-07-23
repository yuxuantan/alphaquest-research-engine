# afternoon_signed_counterflow_1530

Afternoon two-sided VWAP-deviation reversion with signed-volume counterflow through 15:30 ET.

Entry: `vwap_deviation_orderflow_reversion`. Stop: `sweep_extreme`. Target: `fixed_r`.


Rescue 1: parameter-space-only rescue. It preserves the VWAP-deviation counterflow reversion mechanic and changes only declared thresholds, stop offsets, and fixed-R targets.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_vwap_deviation_orderflow_reversion/afternoon_signed_counterflow_1530/rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.
