# Methodology Audit - NQ Cboe VXN/VIX Dispersion Intraday

Verdict: FAIL

## Edge And Source Contract
This campaign tests NQ-specific lagged relative Nasdaq-versus-S&P implied-volatility dispersion using Cboe VXN and VIX daily histories. NQ Sierra 1-minute RTH bars are used for fixed-time intraday execution.

## Lookahead Controls
- VIX and VXN observations are daily closes mapped strictly before each NQ session date.
- Same-day Cboe closes are unavailable and not used.
- Signals use only the configured completed NQ bar and enter no earlier than the next bar open.
- No final session high/low, final VWAP, future return, or post-entry Cboe value is used.

## Parameter Discipline
- Exactly five variants were authored before NQ testing.
- Each variant used one entry parameter, one stop parameter, and one take-profit parameter.
- Variants tested 18 or 27 combinations, inside the declared 8-120 range.
- Selected ES rescue parameter spaces were adopted as predeclared NQ baselines before any NQ PnL was inspected.
- No NQ rescue, date exclusion, threshold pruning, or post-result mechanics change was used.

## Failure Evidence
- `high_vxn_vix_ratio_short_1000` failed core (2/27); top net 645.0, PF 1.0988505747126436, trades 123, MAR 0.3553882371790671.
- `rising_vxn_vix_ratio_short_1030` failed core (0/27); top net -1210.0, PF 0.9168670559945036, trades 96, MAR -0.1481573766542553.
- `low_vxn_vix_ratio_long_1130` failed core (5/18); top net 1061.25, PF 1.1050742574257426, trades 110, MAR 0.870624124800208.
- `falling_vxn_vix_ratio_long_1200` failed core (4/27); top net 615.0, PF 1.074726609963548, trades 84, MAR 0.18338133041675958.
- `high_vxn_minus_vix_short_1330` failed core (7/18); top net 407.5, PF 1.0491852745926373, trades 102, MAR 0.19577137277823228.

## Final Decision
FAIL. The edge did not satisfy the required core profitability-density gate on NQ. No candidate strategy report was created.
