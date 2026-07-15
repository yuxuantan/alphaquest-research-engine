# Methodology audit - NQ prior value-area orderflow rejection

Verdict: FAIL.

Rejected before staged NQ PnL by the pre-PnL density screen. The declared five-variant family had 33 of 42 entry-grid rows pass all density windows, but `afternoon_large20_two_sided_rejection` had 0 of 9 passing rows because the latest-252-session count topped out at 45 signals and the strictest full-history rate was 47.54 signals/year. Dropping that sparse afternoon variant after seeing the screen would be post-result narrowing, so the full campaign is rejected.

No stop/target outcome, trade log, equity curve, limited core, monkey test, WFA, Monte Carlo, simulated incubation, acceptance OOS, final holdout PnL, or candidate report was produced.

- Source ES campaign: `es_prior_value_area_orderflow_rejection`.
- NQ port keeps the same five rejection mechanics and modules.
- Duplicate screen: distinct from NQ value-area acceptance continuation, POC magnet, prior high/low breakout, prior-day stop-run, session-extreme, and VWAP-deviation campaigns; not launched as a new ChartFanatics profile campaign.
- Lookahead control: prior VAH/VAL/POC are frozen from the completed prior RTH session; current probe/rejection/orderflow checks use completed 5-minute bars only; entry occurs next bar open or later.

Density detail: `research_artifacts/nq_prior_value_area_orderflow_rejection_density_audit_20260630.md`.
