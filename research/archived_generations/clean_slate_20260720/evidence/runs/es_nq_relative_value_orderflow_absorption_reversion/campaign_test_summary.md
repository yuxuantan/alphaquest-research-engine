# Campaign Test Summary

Campaign: `es_nq_relative_value_orderflow_absorption_reversion`

Decision: **FAIL**

Updated: 2026-06-18T23:46:49

## Outcome

All five originals failed `limited_core_grid_test`. The one-time per-variant rescues were run for all five failed variants; three rescues failed `limited_core_grid_test`, and two rescues reached WFA after passing limited core and limited monkey but failed `walk_forward_analysis`.

No run reached WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## Best Limited-Core Rows

- Best original by top net: `midday60_two_sided_absorption_1400/run1` with 17/81 profitable combinations, 5 benchmark-passing combinations, top net `3872.5`, PF `1.3575715604801477`, MAR `1.333698925366294`, and trades/year `90.65263168412297`.
- Best rescue by top net: `midday60_two_sided_absorption_1400/rescue1` with 71/81 profitable combinations, 16 benchmark-passing combinations, top net `4457.5`, PF `1.4503662541045719`, MAR `1.4420098992321169`, and trades/year `86.52113528541615`.

## WFA Failures

- `midday60_two_sided_absorption_1400/rescue1`: stitched OOS trades `40`, PF `0.7169466764061359`, MAR `-0.6975521321854036`, trades/year `40.80309072008192`, net `-1937.5`, reason `profit_factor_lt_1.2;mar_lt_0.4;trades_per_year_lt_50;expectancy_not_positive`.
- `morning30_outperform_absorption_short_1030/rescue1`: stitched OOS trades `0`, PF `0.0`, MAR `0.0`, trades/year `0.0`, net `0.0`, reason `early_exit_no_oos_trades_or_no_profitable_is_selection`.

## Artifacts

- `campaign_results.csv`
- `trade_logs_manifest.csv`
- `equity_curves_manifest.csv`
- `wfa_table.csv`
- `monte_carlo_summary.json`
