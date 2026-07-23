# NQ CFTC TFF Hedging Pressure Campaign Summary

Verdict: FAIL.

Rejected before staged NQ PnL: 14/15 declared entry-threshold rows failed the pre-PnL density gate. Only broad_negative_pressure_short_1100 at threshold -25000 cleared all windows. Several positive and extreme negative/positive thresholds had zero signals in the deterministic limited-core proxy, with minimum full-history density 11.17 signals/year and minimum limited-core density 0.00. Dropping the sparse thresholds or retaining the single passing threshold after this screen would be post-result narrowing of the declared five-variant edge. No NQ PnL was inspected.

Density summary:

| variant | rows | pass rows | min full/year | min limited/year | min latest-252 | failed thresholds | verdict |
|---|---:|---:|---:|---:|---:|---|---|
| `broad_negative_pressure_short_1100` | 3 | 1 | 26.59 | 0.00 | 107 | -50000.0, -100000.0 | FAIL |
| `broad_positive_pressure_long_1100` | 3 | 0 | 30.39 | 3.80 | 66 | 25000.0, 47442.0, 75000.0 | FAIL |
| `extreme_negative_pressure_short_1330` | 3 | 0 | 11.17 | 0.00 | 43 | -75000.0, -150000.0, -250000.0 | FAIL |
| `extreme_positive_pressure_long_1330` | 3 | 0 | 16.56 | 0.00 | 39 | 125000.0, 175000.0, 250000.0 | FAIL |
| `high_positive_pressure_long_0935` | 3 | 0 | 19.22 | 0.00 | 51 | 75000.0, 98748.0, 150000.0 | FAIL |

Density audit: `research_artifacts/nq_cftc_tff_hedging_pressure_density_audit_20260630.md`.

No staged PnL, monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run because the declared parameter space failed the pre-PnL density gate.
