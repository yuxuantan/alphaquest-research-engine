# NQ Chicago Fed CFNAI Activity Pullback Methodology Audit

Date: 2026-06-30

Verdict before testing: approved for staged testing only. No PnL evidence has been inspected for the NQ campaign before declaring the five variants and parameter space.

## Duplicate Check

No active NQ CFNAI activity-pullback campaign or NQ staged result was found in `campaigns/`, `backtest-campaigns/`, or `research_ledger.csv`. The ES CFNAI family is already failed, so this is a symbol-transfer test with a weak prior, not an independent alpha claim.

## Timing And Lookahead

- CFNAI rows are assigned only when `eligible_date <= session_date`.
- Entry signals use the completed 1-minute RTH bar ending at the configured signal time.
- Engine execution occurs no earlier than next bar open.
- No final session range, final VWAP, future CFNAI row, or post-entry price path is used for entry.
- All variants force-flatten at 15:55 ET, before the configured 16:59:59 ET futures close.

## Parameter Discipline

- Entry parameters: `driver_max` and `max_session_return_bps`.
- Stop parameter: `stop_pct`.
- Take-profit parameter: `target_r_multiple`.
- Total combinations per variant: 81.

## Pre-PnL Density

The density audit is `research_artifacts/nq_chicagofed_cfnai_activity_pullback_density_audit_20260630.md`. All declared entry-grid corners exceeded 50 signals/year before any PnL testing.

## Execution Realism

NQ tick size is 0.25, point value is 20.0, one contract is used, commission is 2.5 per contract, and one tick of slippage is configured. Same-bar stop/target ordering remains governed by the shared engine policy.

## Outcome

FAIL. All five variants failed `limited_core_grid_test`; best profitable-iteration rate was 0.4691 versus the 0.70 gate. No downstream stage was run, and no candidate report was created.

