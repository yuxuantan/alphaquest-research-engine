# NQ Pre-Holiday Effect Campaign Summary

Verdict: FAIL.

Rejected before staged NQ PnL: 6/9 declared entry rows failed the sparse-event pre-PnL density gate. The unconditional 10:00, 12:00, and 15:00 variants were dense enough, but all low-range rows and all momentum-confirmed rows failed at least one density window; minimum full-history density was 0.39 signals/year, minimum limited-core density was 0.00, and minimum latest-window count was 0. Dropping the filtered variants or retaining only the unconditional rows after this screen would be post-result narrowing of the declared five-variant edge. No NQ PnL was inspected.

Density summary:

| variant | rows | pass rows | min full/year | min limited/year | min latest-252 | failed entry values | verdict |
|---|---:|---:|---:|---:|---:|---|---|
| `preholiday_late_long_1500` | 1 | 1 | 9.20 | 7.79 | 10 | none | PASS_DENSITY_ONLY |
| `preholiday_low_range_midday_long_1200` | 3 | 0 | 0.39 | 0.00 | 0 | 35.0, 55.0, 75.0 | FAIL |
| `preholiday_midday_long_1200` | 1 | 1 | 9.20 | 7.79 | 10 | none | PASS_DENSITY_ONLY |
| `preholiday_momentum_confirmed_midday_long_1200` | 3 | 0 | 3.69 | 3.24 | 7 | 0.0, 10.0, 20.0 | FAIL |
| `preholiday_open_long_1000` | 1 | 1 | 9.20 | 7.79 | 10 | none | PASS_DENSITY_ONLY |

Density audit: `research_artifacts/nq_preholiday_effect_density_audit_20260630.md`.

No staged PnL, monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run because the declared five-variant parameter space failed the pre-PnL density gate.
