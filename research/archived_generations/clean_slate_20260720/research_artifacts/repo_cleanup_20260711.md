# Repository Cleanup Audit

Status: **APPLIED**

Reclaimed: `7.46 GiB`
Generated files removed: `3170`
Superseded error runs removed: `5`

## Removed Payload Classes

- `validation_cleaned_frames`: 103 files, 2476.7 MiB
- `validation_feature_frames`: 103 files, 1843.7 MiB
- `validation_tick_windows`: 76 files, 2568.7 MiB
- `monkey_iteration_results`: 230 files, 514.4 MiB
- `wfa_monkey_iteration_results`: 7 files, 17.1 MiB
- `incubation_monkey_iteration_results`: 0 files, 0.0 MiB
- `monte_carlo_path_events`: 7 files, 105.2 MiB
- `monte_carlo_path_trades`: 7 files, 52.3 MiB
- `generated_html_reports`: 1673 files, 47.2 MiB
- `core_grid_iteration_trades`: 37 files, 4.2 MiB
- `core_grid_iteration_daily`: 37 files, 0.1 MiB

## Removed Runs

- `backtest-campaigns/nq_small_cap_relative_rotation/iwm_1d_strength_long_1000/NQ/run1` -> kept `backtest-campaigns/nq_small_cap_relative_rotation/iwm_1d_strength_long_1000/NQ/run2`
- `backtest-campaigns/nq_small_cap_relative_rotation/iwm_1d_weakness_short_1000/NQ/run1` -> kept `backtest-campaigns/nq_small_cap_relative_rotation/iwm_1d_weakness_short_1000/NQ/run2`
- `backtest-campaigns/nq_small_cap_relative_rotation/iwm_5d_strength_long_1030/NQ/run1` -> kept `backtest-campaigns/nq_small_cap_relative_rotation/iwm_5d_strength_long_1030/NQ/run2`
- `backtest-campaigns/nq_small_cap_relative_rotation/iwm_5d_weakness_short_1130/NQ/run1` -> kept `backtest-campaigns/nq_small_cap_relative_rotation/iwm_5d_weakness_short_1130/NQ/run2`
- `backtest-campaigns/nq_small_cap_relative_rotation/iwm_attention_strength_long_1330/NQ/run1` -> kept `backtest-campaigns/nq_small_cap_relative_rotation/iwm_attention_strength_long_1330/NQ/run2`

## Retained Evidence

- authored campaigns and strategy modules
- research ledgers and methodology audits
- effective/source configs and run manifests
- campaign, variant, stage, core-grid, monkey, WFA, and Monte Carlo summaries
- fixed-config trade logs and equity CSVs
- WFA stitched OOS trade logs
- compact validation trades, conditions, bar windows, exit audits, and checks
