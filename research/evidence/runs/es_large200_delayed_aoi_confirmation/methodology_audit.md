# Methodology Audit: es_large200_delayed_aoi_confirmation

Verdict: FAIL

Pre-test controls:
- Eight variants were declared before staged PnL testing in `campaigns/es_large200_delayed_aoi_confirmation/campaign.yaml`.
- Variant expansion beyond five was justified in `variant_expansion_rationale` before testing.
- The pre-PnL density audit was written to `research_artifacts/es_large200_delayed_aoi_confirmation_density_audit_20260622.md`.
- Grid dimensions were fixed at two entry tunables, one stop tunable, and one target tunable, for 81 combinations per variant.
- Data source was the derived local 1-minute Sierra true-VAP/overnight/footprint plus strict large200 SCID record-proxy cache.
- Signals use completed large200 event bars, one completed confirmation bar, and next-bar execution through `large_record_delayed_aoi_confirmation`.

Result:
- All eight variants failed `limited_core_grid_test`.
- No variant reached monkey testing, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
- No rescue was used.

Failure interpretation:
The delayed large200 AOI confirmation edge is rejected as tested. The best top configuration was `market_aoi_delayed_trap_1500` with 0/81 profitable iterations, top net -1527.5, top PF 0.8557601510859302, and failure reason `min_total_net_profit;max_consecutive_losses`. This is not a robust parameter-stable edge and it did not clear the first objective rejection gate.
