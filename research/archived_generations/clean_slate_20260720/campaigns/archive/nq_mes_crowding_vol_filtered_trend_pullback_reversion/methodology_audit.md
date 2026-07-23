# Methodology Audit - NQ MES-Crowding Volatility-Filtered Trend-Pullback Reversion

Verdict: FAIL

## Edge And Source Contract
This campaign ported the strongest ES MES-crowding volatility-veto family to the NQ execution leg. NQ OHLCV supplied the trend, pullback, fills, stops, targets, and PnL. MES participation was used only as an explicitly documented cross-index micro-participation proxy because no native MNQ participation cache was available locally.

## Lookahead Controls
- MES participation ranks use same-clock prior-session history only.
- Signals use the completed 10:29-10:30 ET bar for a 10:30 ET decision and next-bar-open-or-later entry.
- The NQ trend window ends before the NQ pullback/crowding lookback.
- Lagged NQ volatility gates come from prior-session feature rows only.
- No future NQ return, final session high/low, final VWAP, post-entry MES/NQ orderflow, or current-session realized volatility is used.

## Parameter Discipline
- Exactly five variants were authored before NQ PnL testing.
- Each variant used two entry parameters, one stop parameter, and one take-profit parameter.
- Each variant tested 81 combinations, inside the declared 8-120 range.
- NQ tick thresholds were fixed from the pre-PnL density audit only.
- No rescue, threshold pruning, date exclusion, mechanics change, or parameter adjustment was used after NQ results.

## Failure Evidence
- `exclude_extreme_absret5_trade_morning_1030` failed at limited_monkey_test; core 81/81, top net 26515.0, PF 1.926611916826839, trades 57, MAR 4.992132335746818, monkey failed, median net -620.0, net beat rate 0.8725, drawdown beat rate 0.592375.
- `exclude_extreme_downside20_trade_morning_1030` failed at limited_monkey_test; core 81/81, top net 14000.0, PF 1.5156537753222836, trades 49, MAR 2.162902964325317, monkey failed, median net -415.0, net beat rate 0.821625, drawdown beat rate 0.684875.
- `exclude_extreme_range10_trade_morning_1030` failed at limited_monkey_test; core 75/81, top net 19400.0, PF 1.670005180452426, trades 55, MAR 5.129897708035441, monkey failed, median net -425.0, net beat rate 0.7595, drawdown beat rate 0.48275.
- `exclude_extreme_vol20_trade_morning_1030` failed at limited_monkey_test; core 81/81, top net 12350.0, PF 1.4037927088442046, trades 53, MAR 2.0516844267486056, monkey failed, median net -562.5, net beat rate 0.81175, drawdown beat rate 0.608125.
- `vol_downshift_trade_morning_1030` failed at limited_core_grid_test; core 33/81, top net 16080.0, PF 1.4527664367168802, trades 59, MAR 2.467183033092359.

## Final Decision
FAIL. The cross-index MES-crowding proxy produced attractive limited-core aggregates but did not survive monkey robustness on NQ. No candidate strategy report was created.
