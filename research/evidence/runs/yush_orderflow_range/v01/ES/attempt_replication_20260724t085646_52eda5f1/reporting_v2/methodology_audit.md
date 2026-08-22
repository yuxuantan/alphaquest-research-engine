# Methodology audit

- Campaign: `yush_orderflow_range`
- Variant: `v01`
- Run: `attempt_replication_20260724t085646_52eda5f1`
- ResultBundleV2 verdict: `NEEDS MANUAL REVIEW`
- Diagnostic-only run: `False`
- Reporting trade evidence: `limited_core_grid_test/fixed_config_core_trade_log.csv`
- PASS means candidate strategy only; it is not a trading approval.

## Stage matrix

| Stage | Status | First failed or unresolved criterion |
|---|---|---|
| limited_core_grid_test | error | summary.total_combinations_tested: actual=None; required={"valid_parameter_combination_count": "1 fixed combo or 8-120 tunable combos"} |
| limited_monkey_test | skipped | prior stage failed |
| walk_forward_analysis | skipped | prior stage failed |
| wfa_oos_monkey_test | skipped | prior stage failed |
| wfa_oos_monte_carlo | skipped | prior stage failed |
| simulated_incubation_core | skipped | prior stage failed |
| simulated_incubation_monkey | skipped | prior stage failed |
| acceptance_oos_test | skipped | prior stage failed |

## Evidence integrity

- Required staged artifacts parsed successfully and were hash-recorded.

## Final verdict

NEEDS MANUAL REVIEW
