# ES/NQ Relative-Value Reversion Density Audit - 2026-06-17

Decision: PASS PRE-TEST DENSITY GATE.

This audit checks signal density only. It does not inspect trade PnL, stop/target outcomes, equity curves, WFA performance, or any validation result.

## Edge

Campaign: `es_nq_relative_value_reversion`

Mechanic: fade ES-specific completed return divergence versus NQ. Long ES requires ES underperformance versus NQ and a non-positive completed ES return. Short ES requires ES outperformance versus NQ and a non-negative completed ES return. This rejects the plain NQ-following setup tested in the active failed `es_nq_cross_index_lead_lag` campaign.

Data: `data/cache/orderflow/es_nq_lead_lag_1m_20110103_20260609_full_rth_ny.parquet`

Rows inspected: `1,484,730`

## Signal Counts

| Variant | Signal time ET | Lookback | min spread bps | Signals | Signals/year | Long | Short |
|---|---:|---:|---:|---:|---:|---:|---:|
| `thirty_min_divergence_fade_1000` | 10:00 | 30m | 4 | 1299 | 84.18 | 673 | 626 |
| `thirty_min_divergence_fade_1000` | 10:00 | 30m | 6 | 1166 | 75.56 | 613 | 553 |
| `thirty_min_divergence_fade_1000` | 10:00 | 30m | 8 | 1048 | 67.92 | 554 | 494 |
| `thirty_min_divergence_fade_1030` | 10:30 | 30m | 2 | 1290 | 83.60 | 653 | 637 |
| `thirty_min_divergence_fade_1030` | 10:30 | 30m | 4 | 1043 | 67.59 | 527 | 516 |
| `thirty_min_divergence_fade_1030` | 10:30 | 30m | 6 | 841 | 54.50 | 428 | 413 |
| `thirty_min_divergence_fade_1130` | 11:30 | 30m | 2 | 1160 | 75.18 | 587 | 573 |
| `thirty_min_divergence_fade_1130` | 11:30 | 30m | 3 | 1011 | 65.52 | 508 | 503 |
| `thirty_min_divergence_fade_1130` | 11:30 | 30m | 4 | 871 | 56.45 | 442 | 429 |
| `sixty_min_divergence_fade_1030` | 10:30 | 60m | 6 | 1159 | 75.11 | 586 | 573 |
| `sixty_min_divergence_fade_1030` | 10:30 | 60m | 9 | 991 | 64.22 | 509 | 482 |
| `sixty_min_divergence_fade_1030` | 10:30 | 60m | 12 | 837 | 54.24 | 427 | 410 |
| `sixty_min_divergence_fade_1400` | 14:00 | 60m | 2 | 1115 | 72.26 | 525 | 590 |
| `sixty_min_divergence_fade_1400` | 14:00 | 60m | 2.5 | 1015 | 65.78 | 487 | 528 |
| `sixty_min_divergence_fade_1400` | 14:00 | 60m | 3 | 937 | 60.72 | 448 | 489 |

## Verification

- Exactly five source variants are present under `campaigns/es_nq_relative_value_reversion/variants/`.
- Each variant has `27` parameter combinations.
- Each variant uses one entry tunable, one stop tunable, and one target tunable.
- `python3 -m pytest tests/test_es_nq_relative_value_reversion.py tests/test_es_nq_lead_lag.py tests/test_strategy_modules.py tests/test_preflight.py -q` passed: `150` tests.
- Targeted `python3 -m research.preflight --config <variant config> --skip-tests --json` passed for all five configs.

## Decision

Proceed to staged validation. No paid data was downloaded.
