# ES opening gap orderflow continuation rescue attempt 1 - 2026-06-18

No paid data was downloaded. Rescue used only the local Sierra ES aggregate-orderflow cache.

| variant | original top net | rescue top net | rescue top PF | rescue top trades/year | rescue result |
|---|---:|---:|---:|---:|---|
| `early_large10_gap_hold_continuation_1000` | -2745.0 | -1123.125 | 0.8613425925925926 | 56.28680629873108 | failed limited_core_grid_test |
| `early_signed_gap_hold_continuation_1000` | -3051.25 | -1773.75 | 0.8141697223677318 | 59.4618877535174 | failed limited_core_grid_test |
| `late_morning_large10_gap_hold_continuation_1100` | -407.5 | 686.25 | 1.057068607068607 | 51.32806680543288 | failed limited_core_grid_test |
| `midday_signed_gap_hold_continuation_1200` | -1200.0 | -997.5 | 0.900523560209424 | 53.281183018203606 | failed limited_core_grid_test |
| `morning_signed_gap_hold_continuation_1030` | -5841.25 | -2748.125 | 0.7907386255473063 | 67.5886594052922 | failed limited_core_grid_test |

Decision: completed_failed. All five rescues failed limited_core_grid_test; no WFA or Monte Carlo was reached.
