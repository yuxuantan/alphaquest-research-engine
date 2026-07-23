# Campaign Test Summary

Campaign: `es_opening_drive_inventory_absorption`

Final decision: FAIL

All five original variants failed, and all five allowed per-variant rescues failed. No run reached a passing WFA/Monte Carlo/incubation chain.

| Variant | Run | Terminal stage | Core/monkey pct | Top net | Top PF | Top trades | One-tick stress |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `open30_flow_continuation_1030` | `run1` | `limited_core_grid_test` | `0.38271604938271603` | `730.0` | `2.3394495412844036` | `14` | `None` |
| `open30_flow_continuation_1030` | `rescue1` | `limited_core_grid_test` | `0.35802469135802467` | `791.25` | `2.276209677419355` | `13` | `None` |
| `open60_flow_continuation_1130` | `run1` | `limited_monkey_test` | `0.16333333333333333` | `552.5` | `None` | `42` | `False` |
| `open60_flow_continuation_1130` | `rescue1` | `limited_monkey_test` | `0.20666666666666667` | `587.5` | `None` | `25` | `False` |
| `open30_absorbed_pressure_fade_1015` | `run1` | `limited_core_grid_test` | `0.0` | `-432.5` | `0.45425867507886436` | `9` | `None` |
| `open30_absorbed_pressure_fade_1015` | `rescue1` | `limited_core_grid_test` | `0.0` | `-295.0` | `0.8262150220913107` | `24` | `None` |
| `open60_exhaustion_fade_1300` | `run1` | `limited_core_grid_test` | `0.5555555555555556` | `377.5` | `1.8162162162162163` | `12` | `None` |
| `open60_exhaustion_fade_1300` | `rescue1` | `limited_core_grid_test` | `0.4074074074074074` | `299.375` | `1.6472972972972972` | `12` | `None` |
| `open30_price_flow_divergence_fade_1400` | `run1` | `limited_core_grid_test` | `0.0` | `-202.5` | `0.22115384615384615` | `3` | `None` |
| `open30_price_flow_divergence_fade_1400` | `rescue1` | `limited_core_grid_test` | `0.0` | `-117.5` | `0.8715846994535519` | `21` | `None` |

No `candidate_strategy_report.md` was created because the campaign failed.
