# Methodology Audit - NQ Leveraged ETF Rebalance Pressure

Verdict: FAIL

## Edge And Source Contract
This campaign tests whether mechanical leveraged and inverse Nasdaq ETF rebalancing pressure creates same-direction late-day continuation in NQ after a large completed intraday move. The evidence base is Tuzun (2013, 2014) and Shum, Hejazi, Haryanto, and Rodier (2016). The ES rescue parameter spaces were selected before any NQ PnL inspection and treated only as predeclared NQ baselines.

## Lookahead Controls
- Prior RTH close is known before the current RTH session.
- A signal at the configured HH:MM uses only the completed one-minute bar closing at HH:MM.
- The late-acceleration variant uses only completed bars in the recent window ending at the signal timestamp.
- Entry is no earlier than the next bar open; no final session close, final high/low, final VWAP, future volume profile, or future returns are used.
- All variants flatten at 15:55 ET and produced zero Apex rule violations in their top core rows.

## Parameter Discipline
- Exactly five variants were authored before NQ PnL testing.
- Each variant used no more than two entry parameters, one stop parameter, and one take-profit parameter.
- Parameter spaces ranged from 9 to 27 combinations, inside the declared 8-120 range.
- The pre-PnL density audit passed for all variants, ranging from 62.11 to 174.92 candidate sessions per year across declared corners.
- No NQ rescue, date exclusion, threshold pruning, or post-result mechanics change was used.

## Failure Evidence
- `two_sided_day_move_1430` failed core (0/9); top net -5025.0, PF 0.6993718217170206, trades 206, MAR -0.6549131787243975, failure reason min_total_net_profit.
- `two_sided_day_move_1500` failed core (0/9); top net -4010.0, PF 0.7750350631136045, trades 256, MAR -0.6117376497969091, failure reason min_total_net_profit.
- `up_day_rebalance_long_1500` failed core (0/9); top net -1755.0, PF 0.7770012706480305, trades 147, MAR -0.5551012655920772, failure reason min_total_net_profit.
- `down_day_rebalance_short_1500` failed core (0/9); top net -1830.0, PF 0.7596848325673013, trades 117, MAR -0.5777809466923997, failure reason min_total_net_profit.
- `late_acceleration_two_sided_1530` failed core (0/27); top net -2260.0, PF 0.6869806094182825, trades 125, MAR -0.5698480237944572, failure reason min_total_net_profit.

## Final Decision
FAIL. The edge did not satisfy the required core profitability-density gate on NQ. No candidate strategy report was created.
