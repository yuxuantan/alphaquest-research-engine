# Methodology Audit - NQ MES-Crowding Trend-Pullback Reversion

Verdict: FAIL

## Edge And Source Contract
This campaign ported the ES base trend-filtered MES participation crowding family to the NQ execution leg. NQ OHLCV supplied the trend, pullback, fills, stops, targets, and PnL. MES participation was used only as an explicitly documented cross-index micro-participation proxy because no native MNQ participation cache was available locally.

## Lookahead Controls
- MES participation ranks use same-clock prior-session history only.
- Signals use completed bars at fixed decision times and enter no earlier than next bar open.
- The NQ trend window ends before the NQ pullback/crowding lookback.
- No future NQ return, final session high/low, final VWAP, post-entry MES/NQ orderflow, or current-session future information is used.

## Parameter Discipline
- Exactly five variants were authored before NQ PnL testing.
- Each variant used two entry parameters, one stop parameter, and one take-profit parameter.
- Each variant tested 81 combinations, inside the declared 8-120 range.
- NQ tick thresholds were fixed from the pre-PnL density audit only.
- No rescue, threshold pruning, date exclusion, mechanics change, or parameter adjustment was used after NQ results.

## Failure Evidence
- `afternoon_notional_trend_pullback_reversal_1400` failed at limited_core_grid_test; core 0/81, top net -3070.0, PF 0.7293962097840458, trades 44, MAR -1.0342933123785258.
- `early_afternoon_notional_trend_pullback_reversal_1300` failed at limited_monkey_test; core 81/81, top net 6530.0, PF 1.3137160701417248, trades 49, MAR 1.2259110468547003, monkey failed, median net -730.0, net beat rate 0.661375, drawdown beat rate 0.60225.
- `midday_notional_trend_pullback_reversal_1200` failed at limited_monkey_test; core 79/81, top net 10420.0, PF 1.4245263801181502, trades 53, MAR 2.9780847065647635, monkey failed, median net -542.5, net beat rate 0.787, drawdown beat rate 0.733875.
- `morning_notional_trend_pullback_reversal_1030` failed at limited_core_grid_test; core 42/81, top net 10525.0, PF 1.3692334678126645, trades 67, MAR 1.755177871806761.
- `morning_trade_trend_pullback_reversal_1030` failed at limited_core_grid_test; core 42/81, top net 10585.0, PF 1.3537176274018379, trades 68, MAR 1.5620570382151615.

## Final Decision
FAIL. The cross-index MES-crowding base trend-pullback proxy did not satisfy NQ robustness gates. No candidate strategy report was created.
