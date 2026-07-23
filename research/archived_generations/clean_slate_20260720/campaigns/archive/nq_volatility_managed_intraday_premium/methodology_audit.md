# Methodology Audit - NQ Volatility Managed Intraday Premium

Verdict: FAIL

## Edge And Source Contract
This campaign is a direct NQ port of the ES volatility-managed intraday premium edge. It uses shifted prior-session NQ RTH realized-volatility/range/absolute-move/downside-volatility features from `data/external/nq_lagged_volatility_features_20110103_20260612.csv` and local NQ Sierra 1-minute RTH bars.

## Lookahead Controls
- Volatility state rows are shifted one completed RTH session before the signal date.
- Entry signals use the completed configured entry-time bar; execution is no earlier than next bar open.
- No current-session final range, high, low, close, VWAP, future volatility, or future rank is used.

## Parameter Discipline
- Exactly five variants were authored before testing.
- Each variant used one entry parameter, one stop parameter, and one target parameter.
- Each variant tested 27 combinations, inside the declared 8-120 combination range.
- No rescue, threshold narrowing, date exclusion, or post-result mechanic change was used.

## Failure Evidence
- `low_10d_range_midmorning_long_1030` failed `limited_core_grid_test`: 13/27 profitable combinations; top net 4415.0, top PF 1.3665421336654213.
- `low_20d_vol_open_long_1000` failed `limited_core_grid_test`: 9/27 profitable combinations; top net 2430.0, top PF 1.3993426458504519.
- `low_5d_abs_move_lunch_long_1200` failed `limited_core_grid_test`: 0/27 profitable combinations; top net -30.0, top PF 0.9966024915062288.
- `low_downside20_afternoon_long_1330` failed `limited_core_grid_test`: 1/27 profitable combinations; top net 122.5, top PF 1.0243781094527362.
- `vol_downshift_late_morning_long_1100` failed `limited_core_grid_test`: 5/27 profitable combinations; top net 2655.0, top PF 1.207584050039093.

## Final Decision
FAIL. The edge did not satisfy the required core parameter-stability gate on NQ. No candidate strategy report was created.
