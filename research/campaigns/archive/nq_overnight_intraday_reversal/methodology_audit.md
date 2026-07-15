# Methodology Audit - NQ Overnight Intraday Reversal

Verdict: FAIL

## Edge And Source Contract
This campaign tested NQ overnight-intraday reversal using prior RTH close, current RTH open, and completed opening confirmation windows. Side-only variants were excluded before PnL because they failed the density floor; all tested variants were two-sided and predeclared.

## Lookahead Controls
- Previous RTH close is known before current RTH open.
- Opening confirmation windows are completed before the 10:00 ET signal.
- Entry is next bar open or later, not the signal bar close.
- No current-session final high/low, VWAP, close, or future return is used.

## Parameter Discipline
- Exactly five variants were authored before NQ PnL testing.
- Each variant used two entry parameters, one stop parameter, and one take-profit parameter.
- Each variant tested 54 combinations, inside the declared 8-120 range.
- Thresholds were fixed from the pre-PnL density audit only.
- No rescue, threshold pruning, date exclusion, mechanics change, or parameter adjustment was used after NQ results.

## Failure Evidence
- `first15_confirm_reversal_1000` failed at limited_core_grid_test; core 0/54, top net -870.0, PF 0.9514914970727627, trades 161, MAR -0.1651181998906692.
- `first30_confirm_reversal_1000` failed at limited_core_grid_test; core 0/54, top net -635.0, PF 0.9474989665150889, trades 101, MAR -0.1358032203969636.
- `first30_noncontinuation_1000` failed at limited_core_grid_test; core 0/54, top net -1385.0, PF 0.8251262626262627, trades 99, MAR -0.37407144200750697.
- `first5_confirm_reversal_1000` failed at limited_core_grid_test; core 1/54, top net 225.0, PF 1.0155012056493282, trades 135, MAR 0.047205672990785916.
- `overnight_only_two_sided_1000` failed at limited_core_grid_test; core 0/54, top net -5050.0, PF 0.7954637505062778, trades 222, MAR -0.5276110831383558.

## Final Decision
FAIL. The NQ overnight reversal edge did not satisfy the limited core grid robustness gate. No candidate strategy report was created.
