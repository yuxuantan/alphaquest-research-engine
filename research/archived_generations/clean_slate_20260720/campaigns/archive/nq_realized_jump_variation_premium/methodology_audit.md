# NQ Realized Jump Variation Premium Methodology Audit

Date: 2026-06-30

Verdict before testing: approved for staged testing only. The NQ feature file and five variants were declared before any NQ PnL test for this campaign.

## Duplicate Check

No NQ realized jump-variation campaign or staged result was found. Existing NQ realized semivariance, VIX/VXN, volatility-managed, invariance, and tail-risk campaigns are distinct and already failed. The ES realized-jump family failed, so this is a symbol-transfer test with weak prior evidence.

## Timing And Lookahead

- Realized variance, bipower variation, jump variation, and rolling ranks are shifted by one completed RTH session.
- Entry signals use fixed completed 1-minute bars at the configured signal times.
- Engine execution occurs no earlier than next bar open.
- No current-session jump feature, final range, future rank, or post-entry price path is used for entry.
- All variants force-flatten at 15:55 ET, before the configured 16:59:59 ET futures close.

## Parameter Discipline

- One-sided variants tune one entry parameter: `jump_rank_min`.
- The two-sided variant tunes two entry parameters: `jump_rank_min` and `jump_rank_max`.
- Stop parameter: `stop_pct`.
- Take-profit parameter: `target_r_multiple`.
- One-sided variants have 27 combinations; the two-sided variant has 81 combinations.

## Pre-PnL Density

The density audit is `research_artifacts/nq_realized_jump_variation_premium_density_audit_20260630.md`. All official variants exceeded 50 signals/year before PnL testing. The copied ES high jump-share variant was rejected before PnL because its tightest threshold was under the density floor.

## Execution Realism

NQ tick size is 0.25, point value is 20.0, one contract is used, commission is 2.5 per contract, and one tick of slippage is configured. Same-bar stop/target ordering remains governed by the shared engine policy.

## Outcome

FAIL. Four variants failed `limited_core_grid_test`; `positive_jump_reversal_short_1200` passed core but failed `limited_monkey_test` on max-drawdown beat rate 0.866875 versus the 0.90 gate. No downstream WFA, Monte Carlo, incubation, or acceptance evidence exists.

