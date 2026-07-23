# NQ EPU Policy Uncertainty Initial Density Screen - 2026-06-23

Decision: density-only reform required before any NQ PnL inspection.

This screen counted signal availability for the direct NQ port of the selected ES EPU rescue configs. It did not inspect NQ trade outcomes, stops, targets, WFA, Monte Carlo, or holdout results.

- Feature file: `data/external/nq_epu_policy_uncertainty_features_20110103_20260612.csv`
- Period: 2011-01-03 through 2026-06-12; latest-252 window: 2025-06-09 through 2026-06-12
- Availability rule: latest Daily U.S. EPU observation on or before session date minus 30 calendar days.

## Initial Density Results

| variant | entry combos | total grid combos | min full signals/year | max full signals/year | min latest252 signals | max latest252 signals | density pass | weakest entry params |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `falling_epu_long_1200` | 3 | 18 | 61.4687 | 85.4992 | 75 | 93 | PASS | `{"epu_change_rank_max": 0.25}` |
| `high_epu_ma_short_1330` | 3 | 27 | 63.0233 | 84.7867 | 43 | 79 | FAIL | `{"epu_ma_rank_min": 0.75}` |
| `high_epu_short_1000` | 3 | 27 | 66.4562 | 88.1549 | 63 | 92 | PASS | `{"epu_rank_min": 0.75}` |
| `low_epu_long_1030` | 3 | 18 | 64.2539 | 86.6651 | 34 | 58 | FAIL | `{"epu_rank_max": 0.25}` |
| `rising_epu_short_1130` | 3 | 27 | 98.9718 | 123.4557 | 100 | 119 | PASS | `{"epu_change_rank_min": 0.6}` |

Failure: `low_epu_long_1030` at `epu_rank_max=0.25` had only 34 latest-252 signals and at `epu_rank_max=0.30` had only 44; `high_epu_ma_short_1330` at `epu_ma_rank_min=0.75` had only 43 latest-252 signals. No NQ PnL was inspected before removing those underpowered strict corners.

CSV detail: `research_artifacts/nq_epu_policy_uncertainty_intraday_initial_density_rejected_20260623.csv`
