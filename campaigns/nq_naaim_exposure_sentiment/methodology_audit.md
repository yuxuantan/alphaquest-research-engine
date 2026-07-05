# NQ NAAIM Exposure Sentiment Methodology Audit

Created: 2026-06-30

Verdict before staged testing: TEST

This campaign is a weak-prior NQ symbol-transfer from the failed `es_naaim_exposure_sentiment` family. It is included because no active NQ NAAIM active-manager exposure campaign was found.

## No-Lookahead Contract

The feature file `data/external/nq_naaim_exposure_features_20110103_20260612.csv` was built from NQ RTH sessions and the public NAAIM Exposure Index workbook. Each observation is mapped to the first NQ RTH session at least two business days after the NAAIM observation date. Signals are evaluated on the completed 1-minute bar immediately before the configured entry time, and fills occur no earlier than the next bar open.

## Variant Set

Exactly five variants are declared:

- `level_median_contrarian_1000`
- `level_rank_contrarian_1030`
- `weekly_change_contrarian_1130`
- `zscore_sign_contrarian_1200`
- `ma_distance_contrarian_1400`

Each variant uses `naaim_exposure_sentiment` for entry, `percent_from_entry` for stop loss, and `fixed_r` for take profit. The declared grid is 9 combinations per variant.

## Current Outcome

Final verdict: FAIL

All five variants failed limited_core_grid_test. Best profitable-rate was level_median_contrarian_1000 at 0/9 (0.0), below the 0.70 gate. Across all official variants, 0/45 combinations were profitable, 0 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS.

Apex rule violations were zero in all completed core-grid stages. No candidate strategy report was created.
