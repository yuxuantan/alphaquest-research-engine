# Methodology Audit - NQ Cboe Implied Correlation Intraday

Verdict: FAIL

## Edge And Source Contract
This campaign ports the Cboe implied-correlation state edge to NQ. It uses strictly lagged Cboe COR1M/COR3M daily closes and fixed-time NQ intraday exposure, with the same five mechanics as the ES implied-correlation campaign but NQ contract economics and current NQ validation gates.

## Lookahead Controls
- Cboe implied-correlation observations are mapped strictly before each NQ session date.
- Signals use only the completed NQ bar at the configured timestamp and the lagged daily Cboe state.
- No same-session Cboe close, final NQ high/low, final VWAP, future returns, or post-entry option-state data is used.
- Entry is next bar open or later and all variants flatten by 15:55 ET.

## Parameter Discipline
- Exactly five variants were authored before NQ PnL testing.
- Each variant used one entry parameter, one stop parameter, and one take-profit parameter.
- Each variant tested 27 combinations, inside the declared 8-120 range.
- The pre-PnL density audit passed all declared rank thresholds, with the strictest corner above 69 candidates/year.
- No NQ rescue, date exclusion, threshold pruning, or post-result mechanics change was used.

## Failure Evidence
- `high_cor3m_short_1000` failed at limited_core_grid_test; core 1/27, top net 900.0, PF 1.0424428200896014, trades 146, MAR 0.2994030659974137.
- `low_cor3m_long_1030` failed at limited_monkey_test; core 19/27, top net 1767.5, PF 1.2075748678802114, trades 92, MAR 1.074696194731845, monkey median net -622.5.
- `rising_cor3m_short_1130` failed at limited_core_grid_test; core 8/27, top net 1935.0, PF 1.1109836535704043, trades 139, MAR 0.4233561908060204.
- `falling_cor3m_long_1200` failed at limited_core_grid_test; core 13/27, top net 1800.0, PF 1.193029490616622, trades 129, MAR 1.236046265003683.
- `high_short_term_correlation_short_1330` failed at walk_forward_analysis; core 24/27, top net 5240.0, PF 1.3884358784284656, trades 141, MAR 2.0652794828366114, stitched WFA net -4440.0, PF 0.8561943319838057, MAR -0.37411482767765897, early_exit True.

## Final Decision
FAIL. The edge did not satisfy the required robustness gates on NQ. No candidate strategy report was created.
