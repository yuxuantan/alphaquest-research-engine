# Methodology Audit: nq_max_daily_return_lottery_reversal

Verdict before PnL: APPROVE FOR DENSITY/PREFLIGHT ONLY.

This campaign tests the Bali, Cakici, and Whitelaw MAX daily-return anomaly as a weak-prior NQ futures transfer. The source result is cross-sectional stock evidence, not direct intraday NQ futures evidence, so the campaign must fail closed if any staged gate fails.

## Edge Definition

The tradable state is the largest single completed NQ RTH daily return over a prior lookback, or the average of the five largest completed daily returns over the prior 20 sessions. High-MAX states are interpreted as lottery-salience or overreaction states. One low-MAX variant tests the quiet-premium side.

## No-Lookahead Contract

- The feature builder shifts every MAX value one completed RTH session before it becomes tradable.
- Rolling 252-session ranks are calculated on the shifted prior-session feature series.
- The current signal session's daily return, high, low, close, VWAP, profile, and final range are unavailable to the signal.
- Entries use completed 1-minute bars and staged next-bar execution.
- Stops, targets, costs, flatten time, and prop-rule checks are declared in each config.

## Duplicate Review

Checked against NQ realized skewness, realized jump variation, realized vol-of-vol, daily reversal, daily time-series momentum, 52-week anchor, and intraday capitulation campaigns. This campaign uses maximum prior daily return as a salience state, not a moment/skewness statistic, jump measure, total return, or chart-level anchor.

## Density Review

Pre-PnL density passed: 45/45 entry-threshold/window rows exceeded the configured minimum of 50 signals per year across full history, early limited-core, and latest-252-session windows. See `research_artifacts/nq_max_daily_return_lottery_reversal_density_audit_20260701.md`.

## Failure Rules

If preflight, limited core, monkey, WFA, Monte Carlo, simulated incubation, or acceptance OOS fails, the campaign is FAIL. No rescue is authorized.

## Final Staged Verdict

Verdict: FAIL.

All five frozen variants passed density and preflight, then failed `limited_core_grid_test` in `run1`. Each variant tested 27 official parameter combinations. Profitable-iteration rates ranged from 0.0 to 0.48148148148148145, below the required 0.70 stability threshold. `high_63d_max_fade_short_1200` had 4/27 benchmark-passing cells and `low_5d_max_carry_long_1030` had 10/27 benchmark-passing cells, but isolated cells do not satisfy the staged stability gate. No variant reached limited monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.
