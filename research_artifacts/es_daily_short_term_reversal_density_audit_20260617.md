# ES Daily Short-Term Reversal Density Audit

Date: 2026-06-17

Decision: TEST before backtest, FAIL after staged results.

## Data

- Source: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Scope: local Sierra ES RTH aggregate cache only
- Sessions: 3819
- First session: 2010-12-29
- Last session: 2026-06-09
- Paid downloads: none

## Density Check

The campaign uses completed RTH close-to-close returns and trades at most once
per RTH session. Before backtesting, threshold density was checked from completed
session closes only.

Approximate absolute-return signal densities:

| Lookback | Threshold | Total signals | Signals/year |
|---|---:|---:|---:|
| 1 session | 0.30% | 2502 | 162.0 |
| 1 session | 0.40% | 2152 | 139.3 |
| 1 session | 0.50% | 1890 | 122.4 |
| 1 session | 0.75% | 1322 | 85.6 |
| 3 sessions | 0.75% | 2202 | 142.6 |
| 3 sessions | 1.00% | 1783 | 115.4 |
| 3 sessions | 1.50% | 1100 | 71.2 |
| 5 sessions | 1.00% | 2186 | 141.5 |
| 5 sessions | 1.50% | 1541 | 99.8 |
| 5 sessions | 2.00% | 1069 | 69.2 |

The declared original grids were not rejected for pre-test density. One-sided
1-session variants use lower thresholds to keep expected trade density near or
above the 50 trades/year methodology floor after directional splitting.

## Lookahead Notes

- Returns use only prior completed RTH closes recorded after session completion.
- Current-session close, current-session final range, future VWAP, and future
  volume are not used.
- Signals are emitted on completed 5-minute bars and the engine enters on the
  next bar open or later.

## Outcome

All original and rescue runs failed `limited_core_grid_test`; the density check
does not override the staged failure.
