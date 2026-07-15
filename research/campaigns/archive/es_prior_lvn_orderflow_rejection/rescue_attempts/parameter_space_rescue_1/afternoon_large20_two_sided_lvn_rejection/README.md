# Afternoon Large20 Two-Sided LVN Rejection

Campaign: `es_prior_lvn_orderflow_rejection`

This variant expresses prior-session LVN rejection by freezing approximate low-volume nodes from the completed prior RTH session, waiting for a completed 5-minute ES bar to sweep one of those levels and close back through it, then requiring large20 imbalance in the rejection direction before next-bar execution.

- Direction: two-sided
- Session window: 13:30:00 to 15:30:00 America/New_York
- Stop: signal-bar sweep extreme plus configurable tick offset
- Target: cost-adjusted fixed-R, minimum 1.0R
- Density audit: `research_artifacts/es_prior_lvn_orderflow_rejection_density_audit_20260620.md`

The prior profile is an OHLCV approximation, not true footprint volume-at-price. Any pass remains only a candidate for manual chart review and paper incubation.


## Rescue: parameter_space_rescue_1

All original combinations lost money, with the least-bad row using stricter LVNs, zero large20 threshold, tight stop, and 1R target. Rescue keeps TP unchanged and tests only nearby LVN/flow/stop values to decide whether the afternoon large20 version is simply invalid. Entry, stop, target modules, data, session, costs, and fill assumptions are unchanged. TP values are not widened because the original grid already used only 1.0R or higher targets.
