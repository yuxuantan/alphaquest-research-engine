# ES Intraday Periodicity Persistence Rescue Attempt 1 - 2026-06-17

Decision: FAIL

Scope: per failed variant. The rescue changed only fixed/default parameter values
and declared parameter grids inside the existing `intraday_periodicity_persistence`,
`percent_from_entry`, and `fixed_r` modules. It did not change slot definitions,
direction rule, entry module, stop module, target module, edge thesis, timeframe,
data window, costs, fills, session rules, prop rules, or stage gates.

Original and rescue terminal stage: `limited_core_grid_test`.

| Variant | Run | Profitable combo rate | Benchmark-pass combos | Top net | Top PF | Top trades |
|---|---:|---:|---:|---:|---:|---:|
| `morning_1000_slot_persistence` | `run1` | 0.0 | 0 | -8227.5 | 0.27045001108401684 | 213 |
| `morning_1000_slot_persistence` | `rescue1` | 0.0 | 0 | -5037.5 | 0.18321848398865018 | 135 |
| `morning_1030_slot_persistence` | `run1` | 0.0 | 0 | -4891.25 | 0.7097611630321911 | 237 |
| `morning_1030_slot_persistence` | `rescue1` | 0.0 | 0 | -5408.75 | 0.3779470960322024 | 178 |
| `late_morning_1130_slot_persistence` | `run1` | 0.0 | 0 | -5796.875 | 0.5192307692307693 | 195 |
| `late_morning_1130_slot_persistence` | `rescue1` | 0.0 | 0 | -4667.5 | 0.37348993288590604 | 161 |
| `afternoon_1330_slot_persistence` | `run1` | 0.0 | 0 | -4461.25 | 0.3977387782652717 | 136 |
| `afternoon_1330_slot_persistence` | `rescue1` | 0.0 | 0 | -1923.125 | 0.24657198824681684 | 69 |
| `late_afternoon_1430_slot_persistence` | `run1` | 0.0 | 0 | -5175.0 | 0.3909973521624007 | 175 |
| `late_afternoon_1430_slot_persistence` | `rescue1` | 0.0 | 0 | -2686.25 | 0.5522916666666666 | 166 |

Conclusion: no run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated
incubation, frozen validation, or candidate reporting. No second rescue is
permitted for these variants.
