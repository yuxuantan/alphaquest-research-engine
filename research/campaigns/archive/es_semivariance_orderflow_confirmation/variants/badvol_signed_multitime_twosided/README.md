# Bad-volatility signed-flow multi-time two-sided

Campaign: `es_semivariance_orderflow_confirmation`
Variant: `badvol_signed_multitime_twosided`

## Mechanics

Use the prior downside-semivariance rank as a two-sided state: high ranks permit shorts, low ranks permit longs, and a trade requires matching open-to-signal price movement plus completed signed-flow confirmation.

The signal uses lagged realized-semivariance features from the prior completed RTH session, current-session price movement from the known RTH open, and completed aggregate orderflow ending at the signal bar close. Signals are close-based and therefore execute no earlier than the next bar open in the engine.

## Parameter Space

- Entry tunable 1: `semivar_rank_threshold` in `[0.45, 0.50]`
- Entry tunable 2: `min_orderflow_imbalance` in `[0.0, 0.01, 0.02]`
- Stop tunable: `stop_pct` in `[0.0015, 0.0025, 0.004]`
- Target tunable: `target_r_multiple` in `[0.75, 1.0, 1.5]`

Total combinations: 54.

## Pre-Test Rationale

The two-sided version avoids forcing all semivariance information into a short-only hypothesis. High bad-volatility states express risk-off continuation, while low bad-volatility states express calmer risk-on continuation, both gated by same-session price and flow.

This reformulation was made before staged PnL testing because the original one-checkpoint variants failed the pre-PnL signal-density audit. The core mechanic remains semivariance state plus same-session price and completed aggregate orderflow confirmation.
