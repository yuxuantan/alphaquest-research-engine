# NQ Variance Risk Premium Methodology Audit

Created: 2026-06-30

Verdict before staged testing: TEST

This campaign is a weak-prior NQ symbol-transfer from the failed `es_variance_risk_premium_intraday` family. It is included because no active NQ implied-minus-realized VRP campaign was found.

## No-Lookahead Contract

The feature file `data/external/nq_variance_risk_premium_features_20110103_20260612.csv` was built from the NQ RTH cache and local Cboe VIX history. VIX close and NQ realized variance are shifted one completed RTH session before ranking or signal use. Entry signals are evaluated on the completed 1-minute bar immediately before the configured entry time, and fills occur no earlier than the next bar open.

## Variant Set

Exactly five variants are declared:

- `high_vrp_open_long_1000`
- `low_vrp_open_short_1000`
- `high_vrp_low_realized_midmorning_long_1030`
- `high_vrp_ratio_midday_long_1200`
- `vrp_rising_afternoon_long_1330`

Each variant uses `variance_risk_premium_intraday` for entry, `percent_from_entry` for stop loss, and `fixed_r` for take profit.

## Current Outcome

Final verdict: FAIL

All five variants failed `limited_core_grid_test`. The best profitable-rate was `high_vrp_ratio_midday_long_1200` at 1/27, or 0.037037037037037035, below the 0.70 gate. Across all official variants, 1/189 combinations were profitable, 0 rows passed the benchmark suite, and 0 iterations violated Apex rules.

No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS. No candidate strategy report was created.
