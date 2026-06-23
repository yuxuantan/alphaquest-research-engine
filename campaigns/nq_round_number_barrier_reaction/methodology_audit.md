# Methodology Audit - NQ Round-Number Barrier Reaction

Verdict: FAIL

## Edge And Source Contract
This campaign tested fixed ex-ante NQ psychological price barriers on deterministic 5-minute bars aggregated from local completed 1-minute RTH data. Barrier levels were fixed 25/50/100-point handles and did not use prior-session highs/lows, opening range, VWAP, volume profile, orderflow-derived levels, or future session information.

## Lookahead Controls
- Signals use completed 5-minute bars and enter no earlier than next bar open.
- Breakout variants use only the previous completed close and current completed close.
- Barrier levels are fixed from price handles before the session.
- No final high/low, final VWAP, future range, future orderflow, or post-entry information is used.

## Parameter Discipline
- Exactly five variants were authored before NQ PnL testing.
- Each variant used two entry parameters, one stop parameter, and one take-profit parameter.
- Each variant tested 54 combinations, inside the declared 8-120 range.
- Barrier intervals and buffers were fixed from the pre-PnL density audit only.
- No rescue, threshold pruning, date exclusion, mechanics change, or parameter adjustment was used after NQ results.

## Failure Evidence
- `midday_two_sided_round_reclaim` failed at limited_core_grid_test; core 0/54, top net -165.0, PF 0.985939497230507, trades 137, MAR -0.05206178413268603.
- `morning_round_resistance_reject_short` failed at limited_core_grid_test; core 6/54, top net 1462.5, PF 1.060446373217607, trades 226, MAR 0.36841877236941195.
- `morning_round_support_reclaim_long` failed at limited_core_grid_test; core 4/54, top net 740.0, PF 1.1394910461828465, trades 63, MAR 0.6064477757428589.
- `round_number_downside_breakout_short` failed at limited_core_grid_test; core 23/54, top net 3765.0, PF 1.1719570678237041, trades 225, MAR 1.0981425678429024.
- `round_number_upside_breakout_long` failed at limited_core_grid_test; core 0/54, top net -275.0, PF 0.9475190839694656, trades 110, MAR -0.17238123555622767.

## Final Decision
FAIL. The NQ round-number barrier edge did not satisfy the limited core grid robustness gate. No candidate strategy report was created.
