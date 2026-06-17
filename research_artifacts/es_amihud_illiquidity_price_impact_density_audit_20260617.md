# ES Amihud Illiquidity Price Impact Density Audit

Date: 2026-06-17

Feature rows: 3817
Rank-complete rows: 3740

This is a pre-performance density check only. It counts signal dates from lagged feature ranks before any PnL results are inspected.

## `high_1d_illiq_premium_long_1000`

- threshold=0.25: signals=872, approx_trades_per_year=57.53
- threshold=0.35: signals=1229, approx_trades_per_year=81.09
- threshold=0.45: signals=1605, approx_trades_per_year=105.87

## `high_1d_illiq_stress_short_1030`

- threshold=0.25: signals=872, approx_trades_per_year=57.53
- threshold=0.35: signals=1229, approx_trades_per_year=81.09
- threshold=0.45: signals=1605, approx_trades_per_year=105.87

## `high_5d_illiq_premium_long_1130`

- threshold=0.25: signals=841, approx_trades_per_year=55.69
- threshold=0.35: signals=1189, approx_trades_per_year=78.73
- threshold=0.45: signals=1543, approx_trades_per_year=101.89

## `high_20d_illiq_premium_long_1200`

- threshold=0.25: signals=813, approx_trades_per_year=54.67
- threshold=0.35: signals=1125, approx_trades_per_year=75.29
- threshold=0.45: signals=1417, approx_trades_per_year=94.83

## `two_sided_5d_illiq_state_1330`

- threshold=0.25: signals=2008, approx_trades_per_year=132.48
- threshold=0.35: signals=2697, approx_trades_per_year=177.94
- threshold=0.45: signals=3413, approx_trades_per_year=225.18

Conclusion: PASS density gate. All configured variants are expected to exceed 50 trades/year before performance testing.
