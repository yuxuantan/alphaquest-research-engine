# Methodology Audit: es_nq_nonconfirming_vap_aoi_trap

Verdict: FAIL

Pre-test controls:
- Eight variants were declared before staged PnL testing in `campaigns/es_nq_nonconfirming_vap_aoi_trap/campaign.yaml`.
- Variant expansion beyond five was justified in `variant_expansion_rationale` before testing.
- The pre-PnL density audit was written to `research_artifacts/es_nq_nonconfirming_vap_aoi_trap_density_audit_20260622.md`.
- Grid dimensions were fixed at two entry tunables, one stop tunable, and one target tunable, for 81 combinations per variant.
- Data source was the derived local 1-minute Sierra true-VAP/overnight/footprint plus ES/NQ lead-lag cache; the validation sidecar records 3900 dropped unmatched NQ rows.
- Signals use completed bars and next-bar execution through `nq_nonconfirming_vap_aoi_trap`.

Result:
- All eight variants failed `limited_core_grid_test`.
- No variant reached monkey testing, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
- No rescue was used.

Failure interpretation:
The cross-index non-confirming VAP/AOI trap-reversion edge is rejected as tested. The only positive top configuration was an isolated 1/81 profitable pocket on the 60-minute NQ window and failed concentration/losing-streak gates; the rest were outright negative after costs.
