# NQ Consumer Sentiment State Intraday Methodology Audit

Created: 2026-06-30

Verdict before staged testing: TEST

This campaign is a weak-prior NQ symbol-transfer from the failed `es_consumer_sentiment_state_intraday` family. It is included because no active NQ consumer-sentiment campaign was found.

## No-Lookahead Contract

The feature file `data/external/nq_consumer_sentiment_features_20110103_20260612.csv` was built from the NQ RTH cache and public UMCSENT history. Each NQ session uses only the latest monthly observation on or before session date minus 45 calendar days. Signals are evaluated on the completed 1-minute bar immediately before the configured entry time, and fills occur no earlier than the next bar open.

## Variant Set

Exactly five variants are declared:

- `low_sentiment_long_1000`
- `high_sentiment_short_1030`
- `rising_sentiment_long_1130`
- `falling_sentiment_short_1200`
- `low_sentiment_ma_long_1330`

Each variant uses `consumer_sentiment_state` for entry, `percent_from_entry` for stop loss, and `fixed_r` for take profit. The declared grid is 27 combinations per variant.

## Current Outcome

Final verdict: FAIL

All five variants failed `limited_core_grid_test`. The best profitable-rate was `falling_sentiment_short_1200` at 3/27, or 0.1111111111111111, below the 0.70 gate. Across all official variants, 3/135 combinations were profitable, 1 row passed the benchmark suite, and 0 iterations violated Apex rules.

No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS. No candidate strategy report was created.
