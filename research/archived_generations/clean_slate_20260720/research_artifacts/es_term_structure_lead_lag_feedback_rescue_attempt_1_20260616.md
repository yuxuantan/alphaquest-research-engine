# ES Term-Structure Lead-Lag Feedback Rescue Attempt 1

Date: 2026-06-16

Decision: FAIL.

## Scope

This rescue was allowed because all five original variants failed
`limited_core_grid_test`. The rescue was applied once per failed variant.

Allowed changes only:

- `entry.params.min_front_return_bps` grid/default
- `entry.params.min_spread_gap_bps` grid/default
- `sl.params.stop_pct` grid/default
- `tp.params.target_r_multiple` grid/default

Unchanged:

- edge thesis
- `es_term_structure_lead_lag` entry module
- setup mode, direction permissions, entry time, lookback, and flatten time per variant
- front/deferred contract-selection logic
- `percent_from_entry` stop module
- `fixed_r` target module
- 1-minute timeframe
- data window
- costs, fills, sessions, prop rules, and stage criteria

## Result

All five rescues failed `limited_core_grid_test`.

| Variant | Profitable Combo Rate | Benchmark-Pass Combos | Top Net | Top Trades | Failure |
|---|---:|---:|---:|---:|---|
| `front_premium_reversion_short_1000` | `0.0` | `0` | `-110.0` | `2` | below profitable-combo gate |
| `front_discount_reversion_long_1000` | `0.1111111111111111` | `0` | `15.625` | `5` | below profitable-combo gate; concentration/trade-count failures |
| `late_morning_two_sided_spread_feedback_1130` | `0.07407407407407407` | `0` | `20.0` | `6` | below profitable-combo gate; concentration/trade-count failures |
| `afternoon_confirmed_spread_feedback_1400` | `0.0` | `0` | `-7.5` | `4` | below profitable-combo gate |
| `late_day_two_sided_spread_feedback_1530` | `0.2222222222222222` | `0` | `100.0` | `5` | below profitable-combo gate; trade-count failures |

No rescue reached monkey, WFA, Monte Carlo, simulated incubation, or frozen
validation.

Primary evidence:

- `backtest-campaigns/es_term_structure_lead_lag_feedback/campaign_test_summary.json`
- `backtest-campaigns/es_term_structure_lead_lag_feedback/campaign_results.csv`
