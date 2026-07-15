# NQ Amihud Illiquidity Price Impact Methodology Audit

Created: 2026-06-30

Verdict before staged testing: TEST

This campaign is a weak-prior NQ symbol-transfer from the failed `es_amihud_illiquidity_price_impact` family. It is included because no active NQ Amihud illiquidity or daily return-per-notional-volume price-impact campaign was found.

## No-Lookahead Contract

The feature file `data/external/nq_amihud_illiquidity_features_20110103_20260612.csv` was built from completed NQ RTH bars using NQ point value 20.0. Every tradable Amihud field is shifted one completed RTH session, so a signal date can only use information available after the prior NQ RTH close. Signals are evaluated on the completed 1-minute bar immediately before the configured entry time, and fills occur no earlier than the next bar open.

## Variant Set

Exactly five variants are declared:

- `high_1d_illiq_premium_long_1000`
- `high_1d_illiq_stress_short_1030`
- `high_5d_illiq_premium_long_1130`
- `high_20d_illiq_premium_long_1200`
- `two_sided_5d_illiq_state_1330`

Each variant uses `amihud_illiquidity_state` for entry, `percent_from_entry` for stop loss, and `fixed_r` for take profit. The declared grid is 27 combinations per variant. The original ES `0.25` threshold corner was widened to `0.30` before NQ PnL inspection because the NQ density audit showed the 5-day and 20-day high-illiquidity variants were slightly below 50 signals/year at `0.25`.

## Current Outcome

Final verdict: FAIL

All five variants failed limited_core_grid_test. Best profitable-rate was high_1d_illiq_stress_short_1030 at 11/27 (0.4074074074074074), below the 0.70 gate. Across all official variants, 21/135 combinations were profitable, 4 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS.

Apex rule violations were zero in all completed core-grid stages. No candidate strategy report was created.
