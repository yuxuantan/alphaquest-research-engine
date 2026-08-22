# Methodology audit

- Campaign: `yush_orderflow_range`
- Variant: `v02`
- Run: `attempt_replication_20260801t182032_f6f41448`
- ResultBundleV2 verdict: `FAIL`
- Diagnostic-only run: `False`
- Reporting trade evidence: `limited_core_grid_test/fixed_config_core_trade_log.csv`
- PASS means candidate strategy only; it is not a trading approval.

## Stage matrix

| Stage | Status | First failed or unresolved criterion |
|---|---|---|
| limited_core_grid_test | failed | summary.percentage_profitable_iterations: actual=0.2222222222222222; required={"min": 0.7} |
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
