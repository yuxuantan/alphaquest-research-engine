# Methodology audit — exact Databento Yush range replay

Verdict: **FAIL**.

## Implemented controls

- BacktestEngine canonical event lane replaying direct Databento GLBX trade messages, active outright only, with nanosecond `ts_event` and source-ordinal tie breaks.
- Same-vendor PDH/PDL/PDC, overnight, opening-range, developing volume-profile, delta-profile, and trigger inputs.
- Strict causal AOI eligibility, tap, bubble, order activation, fill, stop/target, and 11:00 flatten sequencing.
- One fixed mechanics set; no result-informed parameter selection.
- Development/holdout split and 1,000 fixed-seed prop-rule Monte Carlo paths.

## Rejection evidence

- Total trades: 281; net profit: $-2,605.00; PF: 0.838.
- Expectancy: $-9.27 per trade and -0.033R.
- Maximum drawdown: $4,657.50; positive-month rate: 30.8%.
- Monte Carlo mean net PnL: $-219.91; breach probability: 100.0%; funded-payout probability: 0.0%.
- High-impact USD calendar applied: False. When absent, the T-5m flatten/entry block cannot be represented and the result fails closed.
- The base case follows the user's zero-slippage exact-price assumption. Static one- and two-tick-per-side cost sensitivities are written separately and do not model path changes.
- Managed brackets inverted at activation: 39; managed targets already reached at activation: 40. The canonical engine preserves this frozen legacy behavior only through an explicit strategy opt-in; it is not the reusable lane default.
- Two pre-existing trigger ambiguities remain frozen for parity: an older same-price large-trade snapshot can mask a later post-tap snapshot, and a developing delta bucket that crossed the threshold before a tap can be recognized after the tap. Correcting either would change mechanics after observing results and requires a separately authorized mechanics revision.

This is not a candidate strategy and must not be promoted or rescued by selecting only long trades, favorable months, trigger types, or confluence subsets after seeing these results.
