# Campaign Test Summary: nq_bls_macro_release_day_drift

Decision: FAIL

Terminal stage: pre_pnl_event_density_screen

Rejected before staged NQ PnL: all nine declared BLS release-date entry rows failed the pre-PnL event-density/data-quality screen. The three unconditional/momentum families had adequate raw calendar frequency but the local NQ cache is missing configured release-day signal bars, while the low-range variant was intrinsically sparse with only 1 to 44 full-window signals (0.0648 to 2.8500/year) and at most 1 signal in the latest 365 days. Dropping the sparse low-range variant or ignoring missing release sessions would narrow the declared five-variant edge after a data screen. No NQ PnL was inspected.

No staged PnL, monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run.
