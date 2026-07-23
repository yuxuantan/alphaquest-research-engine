# Methodology Audit - NQ Prior-Day Stop-Run Reclaim

Verdict: FAIL as of 2026-06-30T12:45:00+08:00.

Source and duplicate review:
- Source ES campaign: `es_prior_day_stop_run_reclaim`, which failed staged validation after its best rescue passed limited core but failed limited monkey robustness.
- The NQ edge is distinct from `nq_prior_session_level_breakout_continuation` and `nq_prior_session_breakout_orderflow_confirmation` because it rejects continuation and requires a completed close back inside the prior RTH high/low.
- The edge is distinct from `nq_overnight_inventory_sweep_reversion` because it uses previous RTH high/low levels, not ETH overnight extremes.
- The campaign is not a Chart Fanatics price-ending test because it uses prior-session levels rather than fixed modulo-100 price barriers.

No-lookahead and execution checks:
- Prior RTH high/low are built from the fully completed previous RTH session only.
- Sweep and reclaim conditions use completed 5-minute bars; any entry must occur no earlier than the next bar open.
- The five configs preserve the ES entry module `pdh_pdl_sweep_reclaim`, percent-from-entry stop, fixed-R target, same-day 15:55 ET flatten, NQ point value, NQ tick value, commission, and one-tick slippage.
- No future session high/low, final VWAP, final range, future volume profile, post-entry orderflow, or PnL-derived filter was used in the source gate.

Pre-PnL density result:
- Detail CSV: `research_artifacts/nq_prior_day_stop_run_reclaim_density_audit_20260630.csv`
- Audit artifact: `research_artifacts/nq_prior_day_stop_run_reclaim_density_audit_20260630.md`
- Required floor: every declared entry-grid corner should reach at least 50 signals/year in both the full-history and limited-core reference windows.
- Result: density failed before PnL. No staged PnL, monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run.

Variant density summary:
- `full_session_two_sided_reclaim`: 6/9 entry corners passed all windows; min full 43.42/year; min limited-core 48.91/year.
- `morning_prior_low_reclaim_long`: 0/9 entry corners passed all windows; min full 16.52/year; min limited-core 17.66/year.
- `morning_prior_high_reject_short`: 0/9 entry corners passed all windows; min full 14.34/year; min limited-core 14.26/year.
- `midday_two_sided_reclaim`: 0/9 entry corners passed all windows; min full 4.49/year; min limited-core 6.11/year.
- `afternoon_two_sided_reclaim`: 0/9 entry corners passed all windows; min full 8.53/year; min limited-core 10.87/year.
