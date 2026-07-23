# NQ Volume-Shock Liquidity Reversal Campaign Summary

Verdict: FAIL.

Rejected before staged NQ PnL: 3/45 declared entry-grid rows failed the pre-PnL density gate. The sparse rows were in midday_symmetric_shock_reversion at min_volume_ratio=2.25 with min_move_ticks 6, 10, and 14; latest-252-session signal count was only 29 for each sparse row, and the 10/14-tick rows also failed the limited-core 50 signals/year gate. Dropping the strict 2.25 volume-ratio tier or the midday variant after this screen would be post-result narrowing of the declared five-variant edge. No NQ PnL was inspected.

Density summary:

| variant | rows | pass rows | min full/year | min limited/year | min latest-252 | verdict |
|---|---:|---:|---:|---:|---:|---|
| `afternoon_symmetric_shock_reversion` | 9 | 9 | 82.81 | 91.70 | 71 | PASS_DENSITY_ONLY |
| `all_day_symmetric_shock_reversion` | 9 | 9 | 219.68 | 197.66 | 241 | PASS_DENSITY_ONLY |
| `midday_symmetric_shock_reversion` | 9 | 6 | 32.19 | 37.36 | 29 | FAIL |
| `morning_down_shock_reversal_long` | 9 | 9 | 130.46 | 93.06 | 176 | PASS_DENSITY_ONLY |
| `morning_up_shock_reversal_short` | 9 | 9 | 129.54 | 90.34 | 159 | PASS_DENSITY_ONLY |

Density audit: `research_artifacts/nq_volume_shock_liquidity_reversal_density_audit_20260630.md`.

No staged PnL, monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run.
