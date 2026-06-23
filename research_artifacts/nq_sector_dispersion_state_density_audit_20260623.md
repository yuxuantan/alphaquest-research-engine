# NQ Sector Dispersion State Density Audit - 2026-06-23

Decision: PASS density gate after density-only pre-PnL grid trim.

This audit counted only signal availability for the final declared entry-grid corners. It did not inspect trade outcomes, stops, targets, WFA, Monte Carlo, or holdout results.

## Density-Only Reform

- `low_1d_dispersion_long_1200`: removed `entry.params.rank_max=0.25`; final entry grid `[0.35, 0.30]`.
- Setup mode, direction, entry time, feature lag, data, costs, stop module, target module, and validation gates were unchanged.
- No NQ PnL was inspected before this trim.

## Data

- NQ source: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Feature output: `data/external/nq_sector_dispersion_features_20110103_20260612.csv`.
- Availability rule: latest sector ETF adjusted close on or before session date minus one business day.
- Feature rows: 3,813; period: 2011-01-03 through 2026-06-12; latest-252 window: 2025-06-09 through 2026-06-12.

## Final Density Results

| variant | entry combos | total grid combos | min full signals/year | max full signals/year | min latest252 signals | max latest252 signals | density pass | weakest entry params |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `falling_5d_dispersion_long_1330` | 3 | 27 | 61.9221 | 85.8231 | 60 | 81 | PASS | `{"rank_max": 0.25}` |
| `high_1d_dispersion_short_1000` | 3 | 27 | 65.5494 | 90.8105 | 74 | 109 | PASS | `{"rank_min": 0.75}` |
| `high_5d_dispersion_short_1030` | 3 | 27 | 65.9380 | 90.3571 | 69 | 93 | PASS | `{"rank_min": 0.75}` |
| `low_1d_dispersion_long_1200` | 2 | 18 | 71.6380 | 83.6856 | 53 | 63 | PASS | `{"rank_max": 0.3}` |
| `rising_1d_dispersion_short_1130` | 3 | 27 | 63.0233 | 87.8310 | 69 | 94 | PASS | `{"rank_min": 0.75}` |

All five final variants clear both the >=50 full-history signals/year screen and the >=50 latest-252-session screen across declared entry-grid corners.

Initial rejected audit: `research_artifacts/nq_sector_dispersion_state_initial_density_rejected_20260623.md`
Detailed CSV: `research_artifacts/nq_sector_dispersion_state_density_audit_20260623.csv`
