# Bad-volatility signed-flow multi-time short

Campaign: `es_semivariance_orderflow_confirmation`
Variant: `badvol_signed_multitime_short`

## Mechanics

On high prior downside-semivariance days, short only after the current RTH session is already below its open and completed rolling signed flow confirms sell pressure at one of four fixed decision times.

The signal uses lagged realized-semivariance features from the prior completed RTH session, current-session price movement from the known RTH open, and completed aggregate orderflow ending at the signal bar close. Signals are close-based and therefore execute no earlier than the next bar open in the engine.

## Parameter Space

- Entry tunable 1: `semivar_rank_threshold` in `[0.45, 0.50]`
- Entry tunable 2: `min_orderflow_imbalance` in `[0.0, 0.005, 0.01]`
- Stop tunable: `stop_pct` in `[0.0015, 0.0025, 0.004]`
- Target tunable: `target_r_multiple` in `[0.75, 1.0, 1.5]`

Total combinations: 54.

## Pre-Test Rationale

High bad-volatility states should represent fragile risk appetite. Requiring current-session downside price action plus negative completed signed flow attempts to enter only when the volatility state is translating into same-day continuation, not merely high realized variance.

This reformulation was made before staged PnL testing because the original one-checkpoint variants failed the pre-PnL signal-density audit. The core mechanic remains semivariance state plus same-session price and completed aggregate orderflow confirmation.

## Rescue Attempt 1

Original profitable rows clustered around wider 0.4% stops and 0.75-1.0R exits; rescue keeps the same entry logic and tests adjacent wider stop values without adding filters.

This rescue changes only fixed defaults and declared parameter ranges. It does not add filters, change modules, change data, change costs, change sessions, or change validation gates.
