# Methodology audit

- Campaign: `yush_orderflow_range`
- Variant: `v03`
- Run: `attempt_pre_pnl_protocol_declaration_20260823t021633_94aff48a`
- ResultBundleV2 verdict: `FAIL`
- Diagnostic-only run: `False`
- Reporting trade evidence: `limited_core_grid_test/fixed_config_core_trade_log.csv`
- PASS means candidate strategy only; it is not a trading approval.

## Stage matrix

| Stage | Status | First failed or unresolved criterion |
|---|---|---|
| limited_core_grid_test | failed | summary.percentage_profitable_iterations: actual=0.0; required={"min": 0.7} |
| limited_monkey_test | skipped | prior scientific-validity stage failed |
| walk_forward_analysis | skipped | prior scientific-validity stage failed |
| wfa_oos_monkey_test | skipped | prior scientific-validity stage failed |
| wfa_oos_monte_carlo | skipped | prior scientific-validity stage failed |
| simulated_incubation_core | skipped | prior scientific-validity stage failed |
| simulated_incubation_monkey | skipped | prior scientific-validity stage failed |
| acceptance_oos_test | skipped | prior scientific-validity stage failed |

## Evidence integrity

- Required staged artifacts parsed successfully and were hash-recorded.

## Final verdict

FAIL
