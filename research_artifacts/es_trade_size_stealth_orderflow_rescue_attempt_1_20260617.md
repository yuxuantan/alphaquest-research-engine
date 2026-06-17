# ES Trade-Size Stealth Orderflow Rescue Audit - 2026-06-17

## Decision

FAIL.

`es_trade_size_stealth_orderflow` produced no candidate strategy. All five
original variants failed `limited_core_grid_test`; all five one-time
parameter-space rescues also failed `limited_core_grid_test`. No run reached
monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen
validation, or candidate reporting.

## Data And Availability

- ES data: existing local Sierra RTH aggregate orderflow cache.
- Cache:
  `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Paid data: none.
- Lookahead control: the entry module uses completed rolling total and
  large-trade orderflow windows ending at the signal bar close; the engine
  enters no earlier than the next 1-minute bar open.

## Rescue Scope

Every failed variant received exactly one rescue attempt. The rescues changed
only numeric `min_large_imbalance`, `min_disagreement`, `stop_pct`, and
`target_r_multiple` parameter spaces. They preserved the trade-size segmented
orderflow edge, entry module, side, entry time, rolling window, large-trade
bucket, residual-flow mode, stop module, target module, timeframe, data window,
costs, fill rules, session rules, prop rules, and validation gates.

## Results

| Variant | Run | Stage | Profitable Combo Rate | Benchmark-Passing Combos | Top Net | Top PF | Top Trades/Year |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| large10_loose_long_1130 | run1 | limited_core_grid_test | 0.0000 | 0 | -111.25 | 0.9707 | 45.66 |
| large10_loose_long_1130 | rescue1 | limited_core_grid_test | 0.0000 | 0 | -997.50 | 0.8366 | 80.94 |
| large10_loose_short_1230 | run1 | limited_core_grid_test | 0.0123 | 0 | 13.75 | 1.0035 | 44.81 |
| large10_loose_short_1230 | rescue1 | limited_core_grid_test | 0.0000 | 0 | -2202.50 | 0.6692 | 73.33 |
| large20_loose_short_1030 | run1 | limited_core_grid_test | 0.5062 | 0 | 1920.00 | 1.3251 | 70.14 |
| large20_loose_short_1030 | rescue1 | limited_core_grid_test | 0.1975 | 0 | 1670.00 | 1.2617 | 73.61 |
| large20_not_aligned_long_1000 | run1 | limited_core_grid_test | 0.0000 | 0 | -1476.25 | 0.5489 | 24.11 |
| large20_not_aligned_long_1000 | rescue1 | limited_core_grid_test | 0.0000 | 0 | -1138.12 | 0.5749 | 26.24 |
| large20_opposite_two_sided_1400 | run1 | limited_core_grid_test | 0.0000 | 0 | -625.00 | 0.8980 | 47.88 |
| large20_opposite_two_sided_1400 | rescue1 | limited_core_grid_test | 0.0000 | 0 | -1917.50 | 0.7111 | 48.57 |

## Artifact Index

- Campaign source: `campaigns/es_trade_size_stealth_orderflow/campaign.yaml`
- Aggregate summary:
  `backtest-campaigns/es_trade_size_stealth_orderflow/campaign_test_summary.json`
- Density audit:
  `research_artifacts/es_trade_size_stealth_orderflow_density_audit_20260617.md`
- Ledger rows: `research_ledger.csv` rows for
  `es_trade_size_stealth_orderflow`
- Methodology note: `methodology_audit.md`

## Active Sweep After Update

- Active campaigns: 47
- Active source variants: 235
- Rescue configs: 235
- Raw variant-level reports: 488
- Aggregate passes: 0
- Active variants missing an original run: 0
- Active variants missing `rescue1`: 0
