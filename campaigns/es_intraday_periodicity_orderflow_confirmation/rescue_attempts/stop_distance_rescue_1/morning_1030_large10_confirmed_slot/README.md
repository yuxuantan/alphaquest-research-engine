# morning_1030_large10_confirmed_slot - Rescue 1

Parameter-space-only rescue for `es_intraday_periodicity_orderflow_confirmation`. Entry module, slot, source window, flow mode, data, costs, fill assumptions, session rules, and validation gates are unchanged from the original variant.

Changes declared before rescue PnL:

- Fixed `entry.params.min_mean_return_bps` increased from `0.5` to `0.75`.
- Stop grid changed to `[0.0015, 0.0025, 0.0035]`.
- Target grid changed to `[1.0, 1.25, 1.5]`.

Rationale: the original settings may have under-expressed the same-clock continuation edge by allowing very weak historical slot tendencies and tight risk geometry. This rescue requires a stronger prior-slot signal while preserving enough expected trade density for the 50 trades/year gate. No new filter or strategy mechanic is introduced.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_intraday_periodicity_orderflow_confirmation/morning_1030_large10_confirmed_slot/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.
