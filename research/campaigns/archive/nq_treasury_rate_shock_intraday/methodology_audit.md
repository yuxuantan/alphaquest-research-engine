# NQ Treasury Rate Shock Intraday Methodology Audit

Created: 2026-06-30

Verdict before staged testing: TEST

This campaign is a weak-prior NQ symbol-transfer from the failed `es_treasury_rate_shock_intraday` family. It is included because no active NQ Treasury yield/curve state campaign was found.

## No-Lookahead Contract

The feature file `data/external/nq_treasury_rate_state_features_20110103_20260612.csv` was built from NQ RTH sessions and daily 2-year/10-year Treasury observations. Each NQ session uses only the latest Treasury observation strictly before the session date. Signals are evaluated on the completed 1-minute bar immediately before the configured entry time, and fills occur no earlier than the next bar open.

## Variant Set

Exactly five variants are declared:

- `rate_up_short_1000`
- `rate_down_long_1000`
- `rate_up_high_level_short_1030`
- `bear_steepening_short_1130`
- `bull_flattening_long_1130`

Each variant uses `treasury_rate_state` for entry, `percent_from_entry` for stop loss, and `fixed_r` for take profit. The declared grids range from 27 to 36 combinations per variant.

## Current Outcome

Final verdict: FAIL

All five variants failed limited_core_grid_test. Best profitable-rate was rate_up_high_level_short_1030 at 19/36 (0.5277777777777778), below the 0.70 gate. Across all official variants, 20/162 combinations were profitable, 0 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS.

Apex rule violations were zero in all completed core-grid stages. No candidate strategy report was created.
