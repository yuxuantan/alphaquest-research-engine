# NQ Sector Dispersion State Initial Density Screen - 2026-06-23

Decision: density-only reform required before any NQ PnL inspection.

This screen counted signal availability for the direct NQ port. It did not inspect NQ trade outcomes, stops, targets, WFA, Monte Carlo, or holdout results.

- Period: 2011-01-03 through 2026-06-12; latest-252 window: 2025-06-09 through 2026-06-12
- Availability rule: latest sector ETF close on or before session date minus one business day.

## Initial Density Results

| variant | entry combos | total grid combos | min full signals/year | max full signals/year | min latest252 signals | max latest252 signals | density pass | weakest entry params |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `falling_5d_dispersion_long_1330` | 3 | 27 | 61.9221 | 85.8231 | 60 | 81 | PASS | `{"rank_max": 0.25}` |
| `high_1d_dispersion_short_1000` | 3 | 27 | 65.5494 | 90.8105 | 74 | 109 | PASS | `{"rank_min": 0.75}` |
| `high_5d_dispersion_short_1030` | 3 | 27 | 65.9380 | 90.3571 | 69 | 93 | PASS | `{"rank_min": 0.75}` |
| `low_1d_dispersion_long_1200` | 3 | 27 | 60.5619 | 83.6856 | 44 | 63 | FAIL | `{"rank_max": 0.25}` |
| `rising_1d_dispersion_short_1130` | 3 | 27 | 63.0233 | 87.8310 | 69 | 94 | PASS | `{"rank_min": 0.75}` |

Failure: `low_1d_dispersion_long_1200` at `rank_max=0.25` had only 44 latest-252 signals. No NQ PnL was inspected before removing that underpowered strict corner.

CSV detail: `research_artifacts/nq_sector_dispersion_state_initial_density_rejected_20260623.csv`
