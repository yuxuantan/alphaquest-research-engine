# Methodology Audit: es_mes_crowding_aoi_trap_reversion

Verdict: FAIL

Pre-test controls:
- Eight variants were declared before staged PnL testing in `campaigns/es_mes_crowding_aoi_trap_reversion/campaign.yaml`.
- Variant expansion beyond five was justified in `variant_expansion_rationale` before testing.
- The pre-PnL density audit was written to `research_artifacts/es_mes_crowding_aoi_trap_reversion_density_audit_20260622.md`.
- Grid dimensions were fixed at two entry tunables, one stop tunable, and one target tunable, for 81 combinations per variant.
- Data source was the derived local 1-minute ES/MES participation-crowding plus true VAP/overnight/footprint cache.
- Signals use completed AOI trap bars and next-bar execution through `mes_crowding_aoi_trap`.

Result:
- All eight variants failed `limited_core_grid_test`.
- No variant reached monkey testing, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
- No rescue was used.

Failure interpretation:
The MES-crowding-at-AOI trap-reversion edge is rejected as tested. The best top configuration was `all_aoi_notional30_delta_1500` with 35/81 profitable iterations, top net 2465.0, top PF 1.3677732189481537, and failure reason ``. This does not clear the first objective rejection gate.
