# Methodology audit - NQ opening-range retest orderflow

Verdict: FAIL.

Rejected before staged NQ PnL by the pre-PnL density screen. The declared five-variant family had 16 of 45 entry-grid rows and only 1 of 5 variants pass all density windows. The only variant that fully cleared density was `or30_large10_absorption_retest_1130`; dropping the other four variants after seeing the screen would be post-result narrowing, so the full campaign is rejected.

No stop/target outcome, trade log, equity curve, limited core, monkey test, WFA, Monte Carlo, simulated incubation, acceptance OOS, final holdout PnL, or candidate report was produced.

- Source ES campaign: `es_opening_range_retest_orderflow`.
- NQ port keeps the same five break-and-retest mechanics and modules.
- Duplicate screen: distinct from NQ immediate opening-range breakout, failed opening-range reclaim, prior-session breakout, and range-compression retest campaigns; not launched as a new ChartFanatics campaign.
- Lookahead control: opening-range high/low are frozen only after the opening window completes; breakout/retest/orderflow checks use completed 5-minute bars only; entry occurs next bar open or later.

Density detail: `research_artifacts/nq_opening_range_retest_orderflow_density_audit_20260630.md`.
