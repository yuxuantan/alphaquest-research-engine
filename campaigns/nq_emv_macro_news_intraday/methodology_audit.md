# NQ EMV Macro-News Intraday Methodology Audit

Created: 2026-06-30

Verdict before staged testing: TEST

This campaign is a weak-prior NQ symbol-transfer from the failed `es_emv_macro_news_intraday` family. It is included because no active NQ EMV macro-news campaign was found.

## No-Lookahead Contract

The feature file `data/external/nq_emv_macro_news_features_20110103_20260612.csv` was built from NQ RTH sessions and monthly FRED EMV category series. Each monthly EMV observation becomes eligible only after observation month-end plus 21 calendar days. Signals are evaluated on the completed 1-minute bar immediately before the configured entry time, and fills occur no earlier than the next bar open.

## Variant Set

Exactly five variants are declared:

- `high_macro_news_short_1030`
- `high_macro_news_rebound_long_1130`
- `rising_macro_news_short_1000`
- `high_interest_news_short_1200`
- `high_labor_news_short_1330`

Each variant uses `emv_macro_news_state` for entry, `percent_from_entry` for stop loss, and `fixed_r` for take profit. The declared grid is 27 combinations per variant.

## Current Outcome

Final verdict: FAIL

All five variants failed limited_core_grid_test. Best profitable-rate was high_interest_news_short_1200 at 18/27 (0.6666666666666666), below the 0.70 gate. Across all official variants, 30/135 combinations were profitable, 3 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS.

Apex rule violations were zero in all completed core-grid stages. No candidate strategy report was created.
