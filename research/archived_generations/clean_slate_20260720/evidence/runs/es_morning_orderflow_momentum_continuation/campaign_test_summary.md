# ES Morning Orderflow Momentum Continuation - Campaign Summary

Decision: **FAIL**

All five original variants and all five one-time parameter-space rescues failed limited_core_grid_test before monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

| Variant | Run | Profitable combo rate | Passing combos | Top net | Top PF | Top MAR | Top trades/year | Terminal |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `first30_signed_flow_continuation_1000` | `rescue1` | 0.2839506172839506 | 11 | 2227.5 | 1.2052995391705068 | 0.6633788420899629 | 79.29228122899285 | limited_core_grid_test |
| `first30_signed_flow_continuation_1000` | `run1` | 0.12345679012345678 | 3 | 2227.5 | 1.2052995391705068 | 0.6633788420899629 | 79.29228122899285 | limited_core_grid_test |
| `first45_large10_flow_continuation_1015` | `rescue1` | 0.13580246913580246 | 2 | 1610.0 | 1.2043795620437956 | 0.8145034020967348 | 57.19344291465558 | limited_core_grid_test |
| `first45_large10_flow_continuation_1015` | `run1` | 0.012345679012345678 | 0 | 153.75 | 1.018574448807007 | 0.04723162874868833 | 57.190474778328046 | limited_core_grid_test |
| `first60_large20_flow_continuation_1030` | `rescue1` | 0.25925925925925924 | 10 | 1542.5 | 1.131612627986348 | 0.31777700821604865 | 90.34131729867396 | limited_core_grid_test |
| `first60_large20_flow_continuation_1030` | `run1` | 0.1111111111111111 | 2 | 1542.5 | 1.131612627986348 | 0.31777700821604865 | 90.34131729867396 | limited_core_grid_test |
| `first60_signed_flow_continuation_1030` | `rescue1` | 0.037037037037037035 | 1 | 607.5 | 1.046847888953152 | 0.16313478237675924 | 98.14056771294797 | limited_core_grid_test |
| `first60_signed_flow_continuation_1030` | `run1` | 0.024691358024691357 | 1 | 607.5 | 1.046847888953152 | 0.16313478237675924 | 98.14056771294797 | limited_core_grid_test |
| `first90_broad_large_alignment_1100` | `rescue1` | 0.0 | 0 | -1003.75 | 0.9276446206523697 | -0.15821282214098814 | 82.9692949768967 | limited_core_grid_test |
| `first90_broad_large_alignment_1100` | `run1` | 0.0 | 0 | -2077.5 | 0.8244242552292415 | -0.5542192891299376 | 89.67442550037063 | limited_core_grid_test |
