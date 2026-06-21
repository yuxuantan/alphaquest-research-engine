# Late-Morning Large10 Two-Sided LVN Rejection

Campaign: `es_prior_lvn_orderflow_rejection`

This variant expresses prior-session LVN rejection by freezing approximate low-volume nodes from the completed prior RTH session, waiting for a completed 5-minute ES bar to sweep one of those levels and close back through it, then requiring large10 imbalance in the rejection direction before next-bar execution.

- Direction: two-sided
- Session window: 10:30:00 to 12:30:00 America/New_York
- Stop: signal-bar sweep extreme plus configurable tick offset
- Target: cost-adjusted fixed-R, minimum 1.0R
- Density audit: `research_artifacts/es_prior_lvn_orderflow_rejection_density_audit_20260620.md`

The prior profile is an OHLCV approximation, not true footprint volume-at-price. Any pass remains only a candidate for manual chart review and paper incubation.


## Rescue: parameter_space_rescue_1

Best original row used a stricter LVN quantile, moderate large10 imbalance, widest stop, and 2R target. Rescue keeps the same large-trade confirmation mechanic, tests neighboring strict LVN quantiles, and expands stop distance because the best row was pinned at the original stop maximum. Entry, stop, target modules, data, session, costs, and fill assumptions are unchanged. TP values are not widened because the original grid already used only 1.0R or higher targets.
