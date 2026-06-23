# Methodology Audit - NQ Daily Short-Term Reversal

Verdict: FAIL

## Edge And Source Contract
This campaign tested NQ daily short-term return reversal using only completed prior RTH closes. It reused the audited ES mechanics template but froze NQ thresholds from pre-PnL signal-density counts only.

## Lookahead Controls
- Return direction uses only RTH closes recorded before the signal session.
- Signals at 10:00, 11:30, 12:00, or 13:30 ET are evaluated on completed 5-minute bars.
- Entry is next bar open or later; no current-session final close, final high/low, VWAP, or future return is used.
- Positions flatten by 15:55 ET and prop forced-flatten rules remain config-driven.

## Parameter Discipline
- Exactly five variants were authored before NQ PnL testing.
- Each variant used one entry parameter, one stop parameter, and one take-profit parameter.
- Each variant tested 27 combinations, inside the declared 8-120 range.
- Thresholds were fixed from the pre-PnL density audit only.
- No rescue, threshold pruning, date exclusion, mechanics change, or parameter adjustment was used after NQ results.

## Failure Evidence
- `prior_1d_gain_reversal_short_1000` failed at limited_core_grid_test; core 0/27, top net -2770.0, PF 0.684869, trades 190, MAR -0.611742.
- `prior_1d_loss_reversal_long_1000` failed at limited_core_grid_test; core 0/27, top net -135.0, PF 0.972079, trades 131, MAR -0.088926.
- `prior_3d_two_sided_reversal_1130` failed at limited_core_grid_test; core 0/27, top net -650.0, PF 0.979716, trades 364, MAR -0.139737.
- `prior_5d_two_sided_reversal_1330` failed at limited_core_grid_test; core 0/27, top net -1910.0, PF 0.92829, trades 355, MAR -0.508734.
- `vol_norm_5d_two_sided_reversal_1200` failed at limited_core_grid_test; core 0/27, top net -1525.0, PF 0.953055, trades 357, MAR -0.211192.

## Final Decision
FAIL. The NQ daily short-term reversal edge did not satisfy the limited core grid robustness gate. No candidate strategy report was created.
