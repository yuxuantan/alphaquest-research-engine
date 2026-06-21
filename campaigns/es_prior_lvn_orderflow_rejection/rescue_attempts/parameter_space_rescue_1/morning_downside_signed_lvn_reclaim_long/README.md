# Morning Downside Signed LVN Reclaim Long

Campaign: `es_prior_lvn_orderflow_rejection`

This variant expresses prior-session LVN rejection by freezing approximate low-volume nodes from the completed prior RTH session, waiting for a completed 5-minute ES bar to sweep one of those levels and close back through it, then requiring signed_volume imbalance in the rejection direction before next-bar execution.

- Direction: long-only
- Session window: 09:35:00 to 11:30:00 America/New_York
- Stop: signal-bar sweep extreme plus configurable tick offset
- Target: cost-adjusted fixed-R, minimum 1.0R
- Density audit: `research_artifacts/es_prior_lvn_orderflow_rejection_density_audit_20260620.md`

The prior profile is an OHLCV approximation, not true footprint volume-at-price. Any pass remains only a candidate for manual chart review and paper incubation.


## Rescue: parameter_space_rescue_1

Best original row used loose LVN selection, zero flow threshold, widest stop, and 2R target. Rescue widens only the stop space and refocuses entry thresholds around the observed best area; TP grid remains unchanged because it already satisfies the 1.0R floor. Entry, stop, target modules, data, session, costs, and fill assumptions are unchanged. TP values are not widened because the original grid already used only 1.0R or higher targets.
