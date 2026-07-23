# Methodology Audit: nq_epu_policy_uncertainty_intraday

Date: 2026-06-23

Verdict: FAIL.

This campaign was a pre-PnL NQ port of `es_epu_policy_uncertainty_intraday`. The low-EPU long variant used the strongest ES low-EPU stop-distance rescue config; the other four variants used the ES parameter-space rescue configs. No NQ PnL was inspected before authoring the campaign or before the density-only grid trim.

## Pre-PnL Density Control

- Initial direct NQ port required density-only reform: `research_artifacts/nq_epu_policy_uncertainty_intraday_initial_density_rejected_20260623.md`.
- The reform removed underpowered strict entry corners for `low_epu_long_1030` and `high_epu_ma_short_1330` before any NQ PnL inspection.
- `low_epu_long_1030` added a non-signal 1.5R target neighbor only to keep the density-trimmed grid at 9 combinations, satisfying the runner's valid-combination floor.
- Final density audit passed: `research_artifacts/nq_epu_policy_uncertainty_intraday_density_audit_20260623.md`.

## No-Lookahead Controls

- A session dated D only uses the latest Daily U.S. EPU observation on or before D minus 30 calendar days.
- Signals use completed one-minute bars and engine entry is next-bar-open or later.
- No final session high/low, final VWAP, future EPU observation, future revision, or post-entry path is used for signal generation.

## Execution Controls

- NQ tick size 0.25, point value 20.0, tick value 5.0.
- Commission 2.5 per contract and 1 tick slippage are configured.
- Same-bar stop/target conflicts use pessimistic OHLC assumptions through the engine.
- All variants force same-day flatten and prohibit overnight exposure through config.

## Outcome

All five variants failed `limited_core_grid_test`. `low_epu_long_1030` had 5/9 profitable combinations and `rising_epu_short_1130` had 8/27, but both missed the required 0.70 profitable-combination gate. No rescue was run after NQ results, and no `candidate_strategy_report.md` was created.
