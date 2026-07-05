# NQ Dollar Risk-Appetite Intraday Methodology Audit

Created: 2026-06-30

Verdict before staged testing: TEST

This campaign is a weak-prior NQ symbol-transfer from the failed `es_dollar_risk_appetite_intraday` family. It is included because no active NQ broad-dollar risk-appetite campaign was found. The existing `nq_usdjpy_safe_haven_spillover` campaign is not treated as a duplicate because it uses a single FX cross, while this campaign uses the Fed nominal broad dollar index.

## No-Lookahead Contract

The feature file `data/external/nq_dollar_risk_appetite_features_20110103_20260612.csv` was built from NQ RTH sessions and public FRED DTWEXBGS history. Each NQ session uses only the latest dollar-index observation on or before session date minus one business day. Signals are evaluated on the completed 1-minute bar immediately before the configured entry time, and fills occur no earlier than the next bar open.

## Variant Set

Exactly five variants are declared:

- `dollar_up_risk_off_short_1000`
- `dollar_down_risk_on_long_1030`
- `high_dollar_up_short_1130`
- `five_day_dollar_up_short_1200`
- `five_day_dollar_down_long_1330`

Each variant uses `dollar_risk_appetite` for entry, `percent_from_entry` for stop loss, and `fixed_r` for take profit. Four variants declare 27 combinations. `high_dollar_up_short_1130` declares two entry parameters and 54 combinations, within the 8-120 methodology range and entry-parameter cap.

## Current Outcome

Final verdict: FAIL

All five variants failed limited_core_grid_test. Best profitable-rate was high_dollar_up_short_1130 at 7/54 (0.12962962962962962), below the 0.70 gate. Across all official variants, 8/162 combinations were profitable, 2 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS.

Apex rule violations were zero in all completed core-grid stages. No candidate strategy report was created.
