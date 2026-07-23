# ES Treasury Rate Shock Intraday Density Audit - 2026-06-16

Status: pre-backtest signal-density audit.

Feature file: `data/external/es_treasury_rate_state_features_20110103_20260609.csv`
Rows: `3817`
Valid rank rows: `3760`
Date range: `2011-01-03` to `2026-06-09`
Span years: `15.43`

No paid data was used. Treasury rates were sourced from the free U.S. Treasury Daily Treasury Rates CSV endpoint.

## `rate_up_short_1000`

- Entry grid cells: `3`
- Cells below 50 trades/year: `0`
- Min/median/max trades/year: `85.9` / `109.7` / `137.9`
- Lowest-density cell `dgs10_change_1d_rank_252>=0.65`: `1325` signals, `85.9`/year
- Lowest-density cell `dgs10_change_1d_rank_252>=0.55`: `1692` signals, `109.7`/year
- Lowest-density cell `dgs10_change_1d_rank_252>=0.45`: `2128` signals, `137.9`/year

## `rate_down_long_1000`

- Entry grid cells: `3`
- Cells below 50 trades/year: `0`
- Min/median/max trades/year: `84.2` / `105.8` / `134.1`
- Lowest-density cell `dgs10_change_1d_rank_252<=0.35`: `1300` signals, `84.2`/year
- Lowest-density cell `dgs10_change_1d_rank_252<=0.45`: `1632` signals, `105.8`/year
- Lowest-density cell `dgs10_change_1d_rank_252<=0.55`: `2069` signals, `134.1`/year

## `rate_up_high_level_short_1030`

- Entry grid cells: `9`
- Cells below 50 trades/year: `0`
- Min/median/max trades/year: `57.1` / `67.5` / `80.4`
- Lowest-density cell `dgs10_change_1d_rank_252>=0.55 & dgs10_rank_252>=0.55`: `881` signals, `57.1`/year
- Lowest-density cell `dgs10_change_1d_rank_252>=0.55 & dgs10_rank_252>=0.5`: `936` signals, `60.7`/year
- Lowest-density cell `dgs10_change_1d_rank_252>=0.5 & dgs10_rank_252>=0.55`: `979` signals, `63.4`/year

## `bear_steepening_short_1130`

- Entry grid cells: `9`
- Cells below 50 trades/year: `0`
- Min/median/max trades/year: `55.0` / `71.2` / `104.9`
- Lowest-density cell `dgs10_change_1d_rank_252>=0.65 & curve_change_1d_rank_252>=0.65`: `849` signals, `55.0`/year
- Lowest-density cell `dgs10_change_1d_rank_252>=0.65 & curve_change_1d_rank_252>=0.55`: `968` signals, `62.7`/year
- Lowest-density cell `dgs10_change_1d_rank_252>=0.55 & curve_change_1d_rank_252>=0.65`: `986` signals, `63.9`/year

## `bull_flattening_long_1130`

- Entry grid cells: `9`
- Cells below 50 trades/year: `0`
- Min/median/max trades/year: `52.8` / `69.7` / `103.9`
- Lowest-density cell `dgs10_change_1d_rank_252<=0.35 & curve_change_1d_rank_252<=0.35`: `815` signals, `52.8`/year
- Lowest-density cell `dgs10_change_1d_rank_252<=0.45 & curve_change_1d_rank_252<=0.35`: `948` signals, `61.4`/year
- Lowest-density cell `dgs10_change_1d_rank_252<=0.35 & curve_change_1d_rank_252<=0.45`: `958` signals, `62.1`/year

Decision: PASS density screen.
