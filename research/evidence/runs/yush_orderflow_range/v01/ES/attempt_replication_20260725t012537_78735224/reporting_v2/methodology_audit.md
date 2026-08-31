# Methodology audit

- Campaign: `yush_orderflow_range`
- Variant: `v01`
- Run: `attempt_replication_20260725t012537_78735224`
- ResultBundleV2 verdict: `FAIL`
- Diagnostic-only run: `False`
- Reporting trade evidence: `limited_core_grid_test/fixed_config_core_trade_log.csv`
- PASS means candidate strategy only; it is not a trading approval.

## Stage matrix

| Stage | Status | First failed or unresolved criterion |
|---|---|---|
| limited_core_grid_test | failed | summary.percentage_profitable_iterations: actual=0.09; required={"min": 0.7} |
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

FAIL
