# NQ FINRA Margin Leverage Methodology Audit

Created: 2026-06-30

Verdict before staged testing: TEST

This campaign is a weak-prior NQ symbol-transfer from the failed `es_finra_margin_leverage` family. It uses official FINRA monthly margin statistics with a conservative 35-calendar-day lag.

## No-Lookahead Contract

The feature file `data/external/nq_finra_margin_leverage_features_20110103_20260612.csv` was built from the NQ RTH cache and official FINRA margin statistics. Session D receives only the latest observation at least 35 calendar days old. The staged data subset starts on 2014-03-07, the first session where all official 120-month rank features are non-null, before any NQ PnL inspection.

## Variant Set

Exactly five variants are declared:

- `rapid_margin_1m_expansion_short_1030`
- `rapid_margin_3m_expansion_short_1130`
- `persistent_margin_12m_expansion_short_1200`
- `debit_credit_ratio_expansion_short_1330`
- `margin_deleveraging_rebound_long_1430`

Each variant uses `finra_margin_leverage` for entry, `percent_from_entry` for stop loss, and `fixed_r` for take profit. The declared grid is 27 combinations per variant.

## Current Outcome

Final verdict: FAIL

Four variants failed `limited_core_grid_test`. `rapid_margin_3m_expansion_short_1130` passed limited core with 22/27 profitable combinations, or 0.8148148148148148, but failed `limited_monkey_test` on max-drawdown robustness: 0.883375 versus the 0.90 gate. Its net-profit beat rate was 0.92225.

No variant reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS. No candidate strategy report was created.
