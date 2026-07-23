# Methodology Audit: es_true_vap_value_area_orderflow_acceptance

Verdict: FAIL

Pre-test controls:
- Eight variants were declared in `campaigns/es_true_vap_value_area_orderflow_acceptance/campaign.yaml` before staged PnL testing.
- Variant expansion beyond five was justified in `variant_expansion_rationale` before testing.
- Grid dimensions were fixed at two entry tunables, one stop tunable, and one target tunable, for 81 combinations per variant.
- Data source was the frozen local 1-minute Sierra true-VAP/orderflow cache.
- Signals use completed bars and next-bar execution through `true_vap_value_area_orderflow_acceptance`.

Result:
- All eight variants failed `limited_core_grid_test`.
- No variant reached monkey testing, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
- No rescue was used.

Failure interpretation:
The direct true-VAP value-area acceptance edge is rejected as tested. The top rows show either outright negative expectancy or isolated low-quality pockets, with no benchmark-passing variant.
