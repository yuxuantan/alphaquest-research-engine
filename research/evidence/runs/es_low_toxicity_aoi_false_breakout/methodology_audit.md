# Methodology Audit: es_low_toxicity_aoi_false_breakout

Verdict: FAIL

Pre-test controls:
- Eight variants were declared before staged PnL testing in `campaigns/es_low_toxicity_aoi_false_breakout/campaign.yaml`.
- Eight-variant expansion was used under the updated policy because all-AOI, market-AOI, opening-range, overnight, value-area, LVN, POC, and largequiet variants are distinct mechanics and cleared pre-PnL density checks.
- The pre-PnL density audit was written to `research_artifacts/es_low_toxicity_aoi_false_breakout_density_audit_20260623.md`.
- Grid dimensions were fixed at two entry tunables, one stop tunable, and one target tunable, for 81 combinations per variant.
- Large-volume-share gates were fixed per variant and were not grid-tuned.
- Signals use completed AOI false-breakout bars, weak completed signed-volume pressure, optional low large20-volume share, and next-bar execution through `low_toxicity_aoi_false_breakout`.

Result:
- All eight variants failed `limited_core_grid_test`.
- No variant reached monkey testing, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
- No rescue was used.

Failure interpretation:
The edge is rejected as tested. The highest profitable-iteration variant was `market_aoi_largequiet_1500` with 37/81 profitable iterations and top net 442.5. The highest top-net variant was `overnight_signedquiet_1500` with top net 1740.0, but it had only 4/81 profitable iterations and failed `max_consecutive_losses;max_best_day_concentration`. Positive pockets were too sparse or concentrated to promote.
