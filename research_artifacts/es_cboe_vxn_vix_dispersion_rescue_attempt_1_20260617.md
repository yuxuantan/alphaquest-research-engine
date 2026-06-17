# ES Cboe VXN/VIX Dispersion Rescue Attempt 1 - 2026-06-17

Campaign: `es_cboe_vxn_vix_dispersion_intraday`

Allowed rescue scope:
- One rescue per failed variant.
- Changed only fixed thresholds and declared parameter space for existing threshold, stop, and target parameters.
- Did not change edge thesis, setup mode, direction, entry time, entry module, stop module, target module, data, costs, session rules, prop rules, fill assumptions, or stage gates.

Original limited core results:

| Variant | Profitable combo rate | Benchmark pass combos | Top net | Top PF | Top trades/year | Decision |
|---|---:|---:|---:|---:|---:|---|
| `high_vxn_vix_ratio_short_1000` | 0.0000 | 0 | -3976.25 | 0.6816 | 105.21 | FAIL |
| `rising_vxn_vix_ratio_short_1030` | 0.0000 | 0 | -4715.00 | 0.7450 | 99.62 | FAIL |
| `low_vxn_vix_ratio_long_1130` | 0.0000 | 0 | -925.00 | 0.9379 | 90.53 | FAIL |
| `falling_vxn_vix_ratio_long_1200` | 0.1111 | 1 | 1320.00 | 1.0866 | 88.69 | FAIL |
| `high_vxn_minus_vix_short_1330` | 0.0000 | 0 | -3537.50 | 0.7562 | 110.47 | FAIL |

Rescue limited core results:

| Variant | Profitable combo rate | Benchmark pass combos | Top net | Top PF | Top trades/year | Decision |
|---|---:|---:|---:|---:|---:|---|
| `high_vxn_vix_ratio_short_1000` | 0.0000 | 0 | -1662.50 | 0.8208 | 68.40 | FAIL |
| `rising_vxn_vix_ratio_short_1030` | 0.0000 | 0 | -3612.50 | 0.7816 | 62.73 | FAIL |
| `low_vxn_vix_ratio_long_1130` | 0.0000 | 0 | -1161.875 | 0.8844 | 130.60 | FAIL |
| `falling_vxn_vix_ratio_long_1200` | 0.2593 | 6 | 2012.50 | 1.2277 | 55.63 | FAIL |
| `high_vxn_minus_vix_short_1330` | 0.0000 | 0 | -726.875 | 0.9344 | 76.49 | FAIL |

Conclusion: The falling-ratio long rescue had a better top row, but the profitable-combo rate was only 25.93%, far below the 70% limited-core stability gate. No variant reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. Campaign decision: FAIL.
