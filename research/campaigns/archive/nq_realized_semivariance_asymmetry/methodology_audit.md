# Methodology Audit - NQ Realized Semivariance Asymmetry

Verdict: FAIL

## Edge And Source Contract
This campaign is a direct NQ port of the ES realized-semivariance asymmetry campaign. It uses NQ Sierra 1-minute RTH bars and a lagged daily NQ realized-semivariance feature file built from completed RTH sessions only.

## Lookahead Controls
- Realized semivariance features are shifted one completed RTH session before use.
- Rolling ranks use only prior completed sessions.
- Entry signals use completed 1-minute bars; execution is next bar open or later.
- No current-session realized semivariance, final session high/low, future return, final VWAP, or overnight exposure is used.
- Same-bar stop/target conflicts use pessimistic OHLC handling.

## Parameter Discipline
- Exactly five variants were authored before testing.
- Four variants tested 18 combinations and one tested 27 combinations, inside the declared 8-120 range.
- Each variant used one entry parameter, one stop parameter, and one take-profit parameter.
- No rescue, date exclusion, threshold pruning, or post-result mechanics change was used.

## Failure Evidence
- `high_1d_badvol_rebound_long_1000` failed core (7/18); top net 1295.0, PF 1.1731283422459893.
- `high_1d_badvol_continuation_short_1030` passed core (27/27) and failed monkey: median net -2000.0, profitable rate 0.216625, core-beats-monkey drawdown rate 0.864.
- `high_downside_share_rebound_long_1130` failed core (11/18); top net 2712.5, PF 1.3297872340425532.
- `high_goodvol_fade_short_1200` passed core (16/18) and failed monkey: median net -1585.0, profitable rate 0.208125, core-beats-monkey drawdown rate 0.858375.
- `two_sided_5d_bad_good_balance_1330` failed core (0/18); top net -48.75, PF 0.9947944474105713.

## Final Decision
FAIL. The edge did not satisfy the required core/robustness gates on NQ. No candidate strategy report was created.
