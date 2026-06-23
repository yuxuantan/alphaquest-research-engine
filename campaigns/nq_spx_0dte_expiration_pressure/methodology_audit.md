# Methodology Audit - NQ SPX 0DTE Expiration Pressure

Verdict: FAIL

## Edge And Source Contract
This campaign tests whether ex-ante SPX 0DTE calendar regimes transmit directional intraday pressure into the NQ futures execution leg. The campaign uses deterministic Cboe listing-rule calendar membership and completed NQ open-to-signal movement only; it does not use option-flow, same-day option price, open-interest, dealer-gamma, final VWAP, future highs/lows, or post-entry information.

## Lookahead Controls
- SPX 0DTE session membership is generated from published listing rules and is known before the session.
- Signals use only the current NQ session open, completed signal-bar close, configured calendar bucket, and completed bar timestamps.
- Entry is next bar open or later after the configured signal time.
- All variants flatten by 15:55 ET and use the configured prop-rule flatten controls.
- Standard monthly expiration Fridays are excluded by config where declared; no post-result date exclusion was added.

## Parameter Discipline
- Exactly five variants were authored before NQ PnL testing.
- Each variant used one entry parameter, one stop parameter, and one take-profit parameter.
- Each variant tested 18 combinations, inside the declared 8-120 range.
- The pre-PnL density audit passed before staged testing.
- No NQ rescue, threshold pruning, mechanics change, or date exclusion was used after results.

## Failure Evidence
- `full_week_down_move_fade_long_1000` failed at limited_core_grid_test; core 0/18, top net -5092.5, PF 0.7029746281714786, trades 27, MAR -2.2735343807649504.
- `full_week_late_move_continuation_1430` failed at walk_forward_analysis; core 18/18, top net 26275.0, PF 2.3013868251609706, trades 72, MAR 23.219010921573528, monkey passed, monkey median net -815.0, stitched WFA net -4677.5, PF 0.9419016271270649, MAR -0.19314201987022375, early_exit True.
- `full_week_up_move_fade_short_1000` failed at limited_core_grid_test; core 4/18, top net 3765.0, PF 1.2036786583716528, trades 48, MAR 3.11842964423106.
- `mwf_two_sided_fade_1030` failed at limited_core_grid_test; core 11/18, top net 8395.0, PF 1.574017094017094, trades 43, MAR 9.848652460043429.
- `tue_thu_two_sided_fade_1030` failed at limited_core_grid_test; core 11/18, top net 10695.0, PF 1.6094017094017095, trades 38, MAR 9.413969979710018.

## Final Decision
FAIL. The edge did not satisfy the required robustness gates on NQ. No candidate strategy report was created.
