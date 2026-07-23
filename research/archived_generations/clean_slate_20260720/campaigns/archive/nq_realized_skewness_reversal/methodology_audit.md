# NQ Realized Skewness Reversal Methodology Audit

Created: 2026-06-30

Verdict before staged testing: TEST

This campaign is a weak-prior NQ symbol-transfer from the failed `es_realized_skewness_reversal` family. It is included because no active NQ lagged realized-skewness reversal campaign was found, but the ES failure prevents treating it as independent supporting evidence.

## Edge And Sources

The edge hypothesis is that lagged realized skewness may proxy payoff-shape preference or crash-asymmetry compensation. The source basis is Amaya, Christoffersen, Jacobs, and Vasquez (2015), Jondeau, Wang, Yan, and Zhang (2020), and Boyer, Mitton, and Vorkink (2010).

## No-Lookahead Contract

The feature file `data/external/nq_lagged_realized_skewness_features_20110103_20260612.csv` was built from `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`.

Every tradable feature is shifted one completed RTH session. A row for session date D can only contain realized skewness information available after session D-1 has closed. Entry signals are evaluated on the completed 1-minute bar immediately before the configured entry time, and fills occur no earlier than the next bar open.

## Variant Set

Exactly five variants are declared:

- `low_1d_skew_open_long_1000`
- `high_1d_skew_open_short_1000`
- `low_3d_skew_midmorning_long_1030`
- `high_3d_skew_midday_short_1200`
- `two_sided_5d_skew_extreme_1330`

Each variant uses `realized_skewness_reversal` for entry, `percent_from_entry` for stop loss, and `fixed_r` for take profit. The declared grid is 27 combinations per variant: one entry parameter, one stop parameter, and one take-profit parameter.

## Pre-PnL Density

The pre-PnL density audit was completed before any staged NQ PnL run. The thinnest declared corner was `low_1d_skew_open_long_1000` at about 60.82 signals/year. No variant was changed after seeing NQ PnL.

## Execution And Prop Rules

NQ assumptions are tick size 0.25, point value 20.0, tick value 5.0, commission 2.5 per contract, and one tick of slippage. Positions must flatten by 15:55 ET under the strategy config and no overnight positions are allowed.

## Current Outcome

Final verdict: FAIL

All five variants failed `limited_core_grid_test`. The best profitable-rate was `low_3d_skew_midmorning_long_1030` at 10/27, or 0.37037037037037035, versus the required 0.70 gate. Across all official variants, 20/135 combinations were profitable, 3 rows passed the limited-core benchmark checks, and 0 Apex-rule violations were reported.

No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS. No candidate strategy report was created.
