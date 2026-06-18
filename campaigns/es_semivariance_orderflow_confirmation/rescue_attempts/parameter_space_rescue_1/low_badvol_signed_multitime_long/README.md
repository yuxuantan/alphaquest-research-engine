# Low bad-volatility signed-flow multi-time long

Campaign: `es_semivariance_orderflow_confirmation`
Variant: `low_badvol_signed_multitime_long`

## Mechanics

On low prior downside-semivariance days, go long only after the current RTH session is above its open and completed rolling signed flow confirms buy pressure at a fixed decision time.

The signal uses lagged realized-semivariance features from the prior completed RTH session, current-session price movement from the known RTH open, and completed aggregate orderflow ending at the signal bar close. Signals are close-based and therefore execute no earlier than the next bar open in the engine.

## Parameter Space

- Entry tunable 1: `semivar_rank_threshold` in `[0.45, 0.50]`
- Entry tunable 2: `min_orderflow_imbalance` in `[0.0, 0.01, 0.02]`
- Stop tunable: `stop_pct` in `[0.0015, 0.0025, 0.004]`
- Target tunable: `target_r_multiple` in `[0.75, 1.0, 1.5]`

Total combinations: 54.

## Pre-Test Rationale

Low downside semivariance should represent a calmer risk-on state. Price above the RTH open plus positive completed signed flow attempts to trade only when that state is actively confirmed by intraday participation.

This reformulation was made before staged PnL testing because the original one-checkpoint variants failed the pre-PnL signal-density audit. The core mechanic remains semivariance state plus same-session price and completed aggregate orderflow confirmation.

## Rescue Attempt 1

Original long-side evidence was close to breakeven only with wider stops and larger targets; rescue tests adjacent stop/target values while preserving low-badvol long confirmation.

This rescue changes only fixed defaults and declared parameter ranges. It does not add filters, change modules, change data, change costs, change sessions, or change validation gates.
