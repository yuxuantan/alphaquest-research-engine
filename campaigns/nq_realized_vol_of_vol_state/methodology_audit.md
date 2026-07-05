# NQ Realized Volatility-of-Volatility State Methodology Audit

Created: 2026-06-30

Verdict before staged testing: TEST

This campaign is a weak-prior NQ symbol-transfer from the failed `es_realized_vol_of_vol_state` family. It is included because no active NQ realized volatility-of-volatility state campaign was found, but the ES failure prevents treating it as independent supporting evidence.

## Edge And Sources

The edge hypothesis is that lagged realized volatility-of-volatility may proxy volatility uncertainty, unresolved stress, or uncertainty compensation in equity-index futures. The source basis is Barndorff-Nielsen and Shephard (2002), Hollstein and Prokopczuk (2018), and Huang, Schlag, Shaliastovich, and Thimme (2018).

## No-Lookahead Contract

The feature file `data/external/nq_realized_vol_of_vol_features_20110103_20260612.csv` was built from `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`.

Every tradable feature is shifted one completed RTH session. A row for session date D can only contain realized volatility-of-volatility information available after session D-1 has closed. Entry signals are evaluated on the completed 1-minute bar immediately before the configured entry time, and fills occur no earlier than the next bar open.

## Variant Set

Exactly five variants are declared:

- `high_1d_vov_premium_long_1000`
- `high_1d_vov_stress_short_1030`
- `low_1d_vov_calm_long_1130`
- `high_5d_vov_premium_long_1200`
- `two_sided_20d_vov_state_1330`

Each variant uses `realized_vol_of_vol_state` for entry, `percent_from_entry` for stop loss, and `fixed_r` for take profit. The declared grid is 27 combinations per variant: one entry parameter, one stop parameter, and one take-profit parameter.

## Pre-PnL Density

The pre-PnL density audit was completed before any staged NQ PnL run. The thinnest declared corner was `low_1d_vov_calm_long_1130` at about 59.53 signals/year. No variant was changed after seeing NQ PnL.

## Execution And Prop Rules

NQ assumptions are tick size 0.25, point value 20.0, tick value 5.0, commission 2.5 per contract, and one tick of slippage. Positions must flatten by 15:55 ET under the strategy config and no overnight positions are allowed.

## Current Outcome

Final verdict: FAIL

All five variants failed `limited_core_grid_test`. The best profitable-rate was `high_1d_vov_premium_long_1000` at 4/27, or 0.14814814814814814, versus the required 0.70 gate. Across all official variants, 5/135 combinations were profitable, 3 rows passed the limited-core benchmark checks, and 0 Apex-rule violations were reported.

No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS. No candidate strategy report was created.
