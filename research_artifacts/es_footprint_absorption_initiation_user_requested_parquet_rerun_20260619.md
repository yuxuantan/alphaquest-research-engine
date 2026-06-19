# ES Footprint Absorption Initiation - User-Requested Parquet Rerun

Date: 2026-06-19
Current-engine refresh completed at: `2026-06-19T07:36:08`

Scope: every active source config that directly references `data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.parquet`.

Rerun command class:

```bash
PYTHONPATH=src:. python3 -m propstack.run_campaign_stages --config <config.yaml> --fast-runtime-defaults
```

Configs rerun: 10 total.

- Five original variants under `campaigns/es_footprint_absorption_initiation/variants/*/config.yaml`
- Five one-time parameter-space rescues under `campaigns/es_footprint_absorption_initiation/rescue_attempts/parameter_space_rescue_1/*/config.yaml`

Outcome: FAIL.

All 10 reruns completed without runner errors and failed at `limited_core_grid_test`. No run reached limited monkey, WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Best original rerun:

- Variant/run: `round_number_footprint_absorption_rejection_1500/run1`
- Profitable combinations: `1 / 81`
- Benchmark-passing combinations: `0`
- Top net profit: `372.5`
- Top PF: `1.0747991967871486`
- Top trades/year: `58.534579970581646`
- Top failure reason: `max_best_day_concentration`

Best rescue rerun:

- Variant/run: `round_number_footprint_absorption_rejection_1500/rescue1`
- Profitable combinations: `4 / 81`
- Benchmark-passing combinations: `1`
- Top net profit: `1416.25`
- Top PF: `1.2434464976364417`
- Top trades/year: `58.534579970581646`
- Campaign still failed because only `4.94%` of parameter combinations were profitable, far below the `70%` limited-core threshold.

Refreshed aggregate artifacts:

- `backtest-campaigns/es_footprint_absorption_initiation/campaign_test_summary.json`
- `backtest-campaigns/es_footprint_absorption_initiation/campaign_test_summary.md`
- `backtest-campaigns/es_footprint_absorption_initiation/campaign_results.csv`
- `backtest-campaigns/es_footprint_absorption_initiation/trade_logs_manifest.csv`
- `backtest-campaigns/es_footprint_absorption_initiation/equity_curves_manifest.csv`
- `backtest-campaigns/es_footprint_absorption_initiation/wfa_table.csv`
- `backtest-campaigns/es_footprint_absorption_initiation/monte_carlo_summary.json`

Fixed-config core trade logs: 10/10 present.

Final decision: FAIL.
