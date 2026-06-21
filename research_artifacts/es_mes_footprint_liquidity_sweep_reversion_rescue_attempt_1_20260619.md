# es_mes_footprint_liquidity_sweep_reversion Rescue Attempt 1

Date: 2026-06-19

Scope: one parameter-space rescue for each of the five failed original variants.

Constraints honored:
- Entry, stop, target modules unchanged.
- Rolling sweep + footprint absorption + MES crowding mechanic unchanged.
- Data, session window, costs, slippage, tick size, point value, next-bar execution, same-bar pessimism, and flatten rules unchanged.
- TP grid unchanged at `[1.0, 1.5, 2.0]`; no target below `1.0R` was used.

Original result: all five originals failed `limited_core_grid_test`.

Rescue result: all five rescues failed `limited_core_grid_test`.

Best rescue: `rolling45_full_session_trade_large10_two_sided/rescue1`, top net `1872.5`, PF `1.1918053777208706`, MAR `1.1075348899720623`, trades/year `104.12761606699735`, profitable-combo rate `0.5555555555555556`.

Decision: FAIL. No second rescue is allowed without explicit user authorization.
