# NQ Prior Value-Area Orderflow Rejection Methodology Audit

Verdict: FAIL.

Rejected before staged NQ PnL by the pre-PnL density screen. The declared five-variant family had 33 of 42 entry-grid rows and 4 of 5 variants pass all density gates, but `afternoon_large20_two_sided_rejection` had 0 of 9 passing rows. No trade logs, equity curves, WFA rows, Monte Carlo paths, simulated incubation, acceptance OOS, or candidate report were produced because no PnL stage was run.

See `campaigns/nq_prior_value_area_orderflow_rejection/methodology_audit.md` and `research_artifacts/nq_prior_value_area_orderflow_rejection_density_audit_20260630.md`.
