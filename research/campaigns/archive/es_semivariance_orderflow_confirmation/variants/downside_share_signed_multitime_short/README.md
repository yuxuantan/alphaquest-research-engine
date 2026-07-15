# Downside-share signed-flow multi-time short

Campaign: `es_semivariance_orderflow_confirmation`
Variant: `downside_share_signed_multitime_short`

## Mechanics

On days after unusually downside-dominated realized variance, short only when the session has moved below the RTH open and completed 60-minute signed flow confirms sell pressure.

The signal uses lagged realized-semivariance features from the prior completed RTH session, current-session price movement from the known RTH open, and completed aggregate orderflow ending at the signal bar close. Signals are close-based and therefore execute no earlier than the next bar open in the engine.

## Parameter Space

- Entry tunable 1: `semivar_rank_threshold` in `[0.45, 0.50]`
- Entry tunable 2: `min_orderflow_imbalance` in `[0.0, 0.01, 0.02]`
- Stop tunable: `stop_pct` in `[0.0015, 0.0025, 0.004]`
- Target tunable: `target_r_multiple` in `[0.75, 1.0, 1.5]`

Total combinations: 54.

## Pre-Test Rationale

A high downside-share state is more directional than raw variance because the prior session risk was concentrated in negative returns. Same-session price and flow confirmation should select days where that risk aversion is continuing intraday.

This reformulation was made before staged PnL testing because the original one-checkpoint variants failed the pre-PnL signal-density audit. The core mechanic remains semivariance state plus same-session price and completed aggregate orderflow confirmation.
