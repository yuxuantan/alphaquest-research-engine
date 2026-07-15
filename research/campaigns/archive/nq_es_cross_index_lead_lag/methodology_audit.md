# Methodology Audit - NQ ES Cross-Index Lead-Lag

Verdict: FAIL

## Edge And Source Contract
This campaign tests the NQ execution-leg mirror of the ES/NQ lead-lag edge: completed ES movement is treated as the information leader, and NQ is traded only when it lags ES by a predeclared completed-return gap. The evidence base is Huth and Abergel (2014), Schmidt, Cestonaro, and Bender (2024), and Michael, Cucuringu, and Howison (2024).

## Lookahead Controls
- Signals use only completed ES and NQ rolling-return columns ending at the configured signal timestamp.
- Entry is no earlier than the next NQ bar open after the signal bar closes.
- The aligned NQ/ES cache is same-clock and RTH-only; no future session high/low, final VWAP, final daily range, or post-signal return is used.
- All variants use America/New_York timestamps and flatten before the configured prop cutoff.

## Parameter Discipline
- Exactly five variants were authored before NQ PnL testing.
- Each variant used two entry parameters, one stop parameter, and one take-profit parameter.
- Parameter spaces ranged from 36 to 81 combinations, inside the declared 8-120 range.
- The pre-PnL density audit passed for every declared entry corner, with minimum density about 53.59 candidates/year.
- No NQ rescue, date exclusion, threshold pruning, or post-result mechanics change was used.

## Failure Evidence
- `early30_two_sided_lag_follow_1000` failed at limited_monkey_test; core 65/81, top net 1942.5, PF 1.1954225352112675, trades 159, MAR 1.1660760743577445, monkey profitable 0.155375, monkey median net -2525.0, net beat rate 0.8925.
- `early15_two_sided_lag_follow_1030` failed at limited_core_grid_test; core 0/54, top net -3185.0, PF 0.6498075865860363, trades 128, MAR -0.6321832638715877.
- `late_morning60_two_sided_lag_follow_1130` failed at limited_core_grid_test; core 0/81, top net -1415.0, PF 0.831044776119403, trades 122, MAR -0.5111499330542261.
- `midday60_confirmed_lag_follow_1230` failed at limited_core_grid_test; core 0/36, top net -1740.0, PF 0.7993079584775087, trades 98, MAR -0.319764174397272.
- `late_day30_confirmed_lag_follow_1530` failed at limited_core_grid_test; core 0/36, top net -1510.0, PF 0.8064102564102564, trades 120, MAR -0.5417389123502457.

## Final Decision
FAIL. The edge did not satisfy the required robustness gates on NQ. No candidate strategy report was created.
