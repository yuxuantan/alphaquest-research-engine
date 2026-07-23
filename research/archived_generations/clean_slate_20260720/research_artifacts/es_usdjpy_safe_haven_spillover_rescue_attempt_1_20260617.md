# ES USD/JPY Safe-Haven Spillover Rescue Attempt 1 - 2026-06-17

Campaign: `es_usdjpy_safe_haven_spillover`

Allowed rescue scope:
- One rescue per failed variant.
- Changed only fixed thresholds and declared parameter space for existing threshold, stop, and target parameters.
- Did not change edge thesis, setup mode, direction, entry time, entry module, stop module, target module, data, costs, session rules, prop rules, fill assumptions, or stage gates.

Original limited core results:

| Variant | Profitable combo rate | Benchmark pass combos | Top net | Top PF | Top trades/year | Decision |
|---|---:|---:|---:|---:|---:|---|
| `yen_appreciation_short_1000` | 0.0000 | 0 | -1160.00 | 0.9126 | 75.88 | FAIL |
| `yen_depreciation_long_1030` | 0.0000 | 0 | -4262.50 | 0.5428 | 96.30 | FAIL |
| `strong_yen_short_1130` | 0.0000 | 0 | -4857.50 | 0.8241 | 225.37 | FAIL |
| `weak_yen_long_1200` | 0.2593 | 0 | 1207.50 | 1.2156 | 51.34 | FAIL |
| `five_day_yen_appreciation_short_1330` | 0.0000 | 0 | -2835.00 | 0.7819 | 80.99 | FAIL |

Rescue results:

| Variant | Terminal stage | Profitable combo rate | Benchmark pass combos | Top net | Top PF | Top trades/year | Decision |
|---|---|---:|---:|---:|---:|---:|---|
| `yen_appreciation_short_1000` | limited_core_grid_test | 0.1481 | 2 | 1070.00 | 1.0739 | 76.05 | FAIL |
| `yen_depreciation_long_1030` | limited_core_grid_test | 0.0000 | 0 | -2272.50 | 0.5859 | 59.68 | FAIL |
| `strong_yen_short_1130` | limited_core_grid_test | 0.5556 | 8 | 4290.00 | 1.1819 | 175.44 | FAIL |
| `weak_yen_long_1200` | limited_monkey_test | 1.0000 | 0 | 1607.50 | 1.3466 | 61.67 | FAIL |
| `five_day_yen_appreciation_short_1330` | limited_core_grid_test | 0.0000 | 0 | -945.00 | 0.8886 | 49.76 | FAIL |

`weak_yen_long_1200/rescue1` was the only run to pass limited core. It failed limited monkey because core-vs-monkey net-profit beat rate was 0.8333333333333334, below the 0.9 benchmark. No run reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
