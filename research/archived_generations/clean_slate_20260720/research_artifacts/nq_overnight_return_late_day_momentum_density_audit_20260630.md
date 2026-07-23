# nq_overnight_return_late_day_momentum Density Audit

- Verdict: `PASS`
- Generated: 2026-06-30
- Method: vectorized session-feature equivalent of `OvernightReturnLateDayMomentumEntry` for one-signal-per-session variants.
- Full window: `2011-01-03` to `2026-06-12` (3813 sessions, 15.13 years)
- Limited-core window: `2011-02-22` to `2012-09-07` (371 sessions, 1.47 years)
- Latest window: `2025-06-09` to `2026-06-12` (252 sessions)
- Declared entry rows tested: `27`
- Passing entry rows: `27`
- Failing entry rows: `0`

## Variant Summary

| variant_id                                 | rows | passing_rows | min_full_signals_per_year | min_limited_signals_per_year | min_latest_signals | max_latest_signals |
| ------------------------------------------ | ---- | ------------ | ------------------------- | ---------------------------- | ------------------ | ------------------ |
| negative_overnight_short_1530              | 3    | 3            | 101.51                    | 106.64                       | 96                 | 99                 |
| opening_reversal_confirmed_1530            | 9    | 9            | 107.46                    | 82.87                        | 109                | 113                |
| penultimate_alignment_1530                 | 9    | 9            | 96.82                     | 70.64                        | 118                | 125                |
| positive_overnight_long_1530               | 3    | 3            | 134.76                    | 121.58                       | 147                | 153                |
| two_sided_overnight_sign_continuation_1530 | 3    | 3            | 236.27                    | 228.23                       | 243                | 252                |

All declared entry rows met the pre-PnL density floor: at least 50 signals/year on full history, at least 50 signals/year on the limited-core shortlist window, and at least 50 signals in the latest 252 sessions.

This density pass only permits staged PnL testing; it is not evidence of profitability.
