# ES Late-Day Market Intraday Momentum - Campaign Summary

Decision: FAIL

All five original variants and all five one-time parameter-space-only rescues failed the limited core-grid profitable-combination gate before WFA completion.

An initial zero-trade run caused by missing prev_rth_close/volume_ratio feature configuration was discarded before rescue and rerun as corrected run1; it is not counted as a strategy failure.

| Variant | Run | Terminal stage | Profitable combos | Top net | Top PF | Top MAR | Top trades |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `first30_to_last30_two_sided` | `run1` | `limited_core_grid_test` | 0.0 | -6765.0 | 0.522414401694317 | -0.6521907594636649 | 253 |
| `first30_to_last30_two_sided` | `rescue1` | `limited_core_grid_test` | 0.0 | -2941.25 | 0.07942097026604068 | -0.6715239155971767 | 72 |
| `first30_to_last30_long_only` | `run1` | `limited_core_grid_test` | 0.0 | -2697.5 | 0.6175115207373272 | -0.5602027192602668 | 137 |
| `first30_to_last30_long_only` | `rescue1` | `limited_core_grid_test` | 0.0 | -742.5 | 0.7933194154488518 | -0.36849485470616317 | 76 |
| `first30_volume_range_conditioned` | `run1` | `limited_core_grid_test` | 0.0 | -3270.0 | 0.6214182344428365 | -0.6379312864576528 | 164 |
| `first30_volume_range_conditioned` | `rescue1` | `limited_core_grid_test` | 0.0 | -912.5 | 0.4296875 | -0.6354910662375328 | 35 |
| `first60_to_last30_two_sided` | `run1` | `limited_core_grid_test` | 0.0 | -5220.625 | 0.4707932083122149 | -0.6325775432073835 | 186 |
| `first60_to_last30_two_sided` | `rescue1` | `limited_core_grid_test` | 0.0 | -2316.25 | 0.08267326732673268 | -0.6722721037081738 | 57 |
| `first30_penultimate_alignment` | `run1` | `limited_core_grid_test` | 0.0 | -1902.5 | 0.5216844751728472 | -0.694778159734456 | 68 |
| `first30_penultimate_alignment` | `rescue1` | `limited_core_grid_test` | 0.0 | -240.0 | 0.1111111111111111 | -0.9019227054311851 | 8 |
