# NQ Cboe SKEW Tail Risk Intraday Methodology Audit

Created: 2026-06-30

Verdict before staged testing: TEST

This campaign is a weak-prior NQ symbol-transfer from the failed `es_cboe_skew_tail_risk_intraday` family. It is included because no active NQ Cboe SKEW option-implied downside-tail skew campaign was found.

## No-Lookahead Contract

The feature file `data/external/nq_cboe_skew_tail_risk_features_20110103_20260612.csv` was built from the NQ RTH cache and official Cboe SKEW history. It merges only the latest Cboe SKEW close strictly before the NQ session date. Signals are evaluated on the completed 1-minute bar immediately before the configured entry time, and fills occur no earlier than the next bar open.

## Variant Set

Exactly five variants are declared:

- `high_skew_short_1000`
- `low_skew_long_1030`
- `rising_skew_short_1130`
- `falling_skew_long_1200`
- `persistent_high_skew_short_1330`

Each variant uses `cboe_skew_tail_risk` for entry, `percent_from_entry` for stop loss, and `fixed_r` for take profit. The declared grid is 27 combinations per variant.

## Current Outcome

Final verdict: FAIL

All five variants failed `limited_core_grid_test`. The best profitable-rate was `high_skew_short_1000` at 0/27, or 0.0, below the 0.70 gate. Across all official variants, 0/135 combinations were profitable, 1 row passed the benchmark suite with zero net profit, and 0 iterations violated Apex rules.

No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS. No candidate strategy report was created.
