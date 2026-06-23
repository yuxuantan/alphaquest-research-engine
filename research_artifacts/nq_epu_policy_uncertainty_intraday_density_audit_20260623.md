# NQ EPU Policy Uncertainty Density Audit - 2026-06-23

Decision: PASS density gate after density-only pre-PnL grid trim.

This audit used the same 30-calendar-day-lagged Daily U.S. EPU feature file and counted only signal availability for the final declared entry-grid corners. It did not inspect trade outcomes, stops, targets, WFA, Monte Carlo, or final holdout performance.

## Density-Only Reform

- `low_epu_long_1030`: removed `entry.params.epu_rank_max=0.25` and `0.30`; final entry grid `[0.35]`.
- `low_epu_long_1030`: added non-signal target neighbor `target_r_multiple=1.5` so the density-trimmed grid keeps 9 total combinations.
- `high_epu_ma_short_1330`: removed `entry.params.epu_ma_rank_min=0.75`; final grid `[0.65, 0.70]`.
- Setup mode, direction, entry time, feature lag, data, costs, stop module, target module, and validation gates were unchanged.
- No NQ PnL was inspected before this trim.

## Data

- NQ source: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Prepared timeframe: 1-minute bars, America/New_York RTH.
- Feature output: `data/external/nq_epu_policy_uncertainty_features_20110103_20260612.csv`.
- Availability rule: latest Daily U.S. EPU observation on or before session date minus 30 calendar days.
- Feature rows: 3,813; period: 2011-01-03 through 2026-06-12; latest-252 window: 2025-06-09 through 2026-06-12.

## Final Density Results

| variant | entry combos | total grid combos | min full signals/year | max full signals/year | min latest252 signals | max latest252 signals | density pass | weakest entry params |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `falling_epu_long_1200` | 3 | 18 | 61.4687 | 85.4992 | 75 | 93 | PASS | `{"epu_change_rank_max": 0.25}` |
| `high_epu_ma_short_1330` | 2 | 18 | 74.2289 | 84.7867 | 67 | 79 | PASS | `{"epu_ma_rank_min": 0.7}` |
| `high_epu_short_1000` | 3 | 27 | 66.4562 | 88.1549 | 63 | 92 | PASS | `{"epu_rank_min": 0.75}` |
| `low_epu_long_1030` | 1 | 9 | 86.6651 | 86.6651 | 58 | 58 | PASS | `{"epu_rank_max": 0.35}` |
| `rising_epu_short_1130` | 3 | 27 | 98.9718 | 123.4557 | 100 | 119 | PASS | `{"epu_change_rank_min": 0.6}` |

All five final variants clear both the >=50 full-history signals/year screen and the >=50 latest-252-session screen across declared entry-grid corners. Each full parameter grid remains either 9, 18, or 27 combinations, within the runner policy floor.

Initial rejected audit: `research_artifacts/nq_epu_policy_uncertainty_intraday_initial_density_rejected_20260623.md`
Detailed CSV: `research_artifacts/nq_epu_policy_uncertainty_intraday_density_audit_20260623.csv`
