# Campaign Test Summary: nq_default_spread_orderflow_risk_premium

Verdict: FAIL

Stage reached: pre_pnl_density_screen. No NQ PnL, WFA, Monte Carlo, or holdout testing was run because the authored five-variant campaign failed signal-density eligibility.

| variant | entry combos | min full signals/year | min latest252 signals | decision |
|---|---:|---:|---:|---|
| `high_spread_large10_long_1230` | 9 | 29.4713 | 0 | FAIL |
| `high_spread_signed_long_1230` | 9 | 3.7568 | 0 | FAIL |
| `tightening_spread_signed_long_1130` | 9 | 11.7885 | 6 | FAIL |
| `two_sided_spread_change_large10_1130` | 9 | 56.1574 | 67 | PASS density only |
| `widening_spread_signed_short_1230` | 9 | 7.1897 | 4 | FAIL |

Campaign rejection: only `two_sided_spread_change_large10_1130` passed density. The campaign cannot be promoted or staged as a one-variant subset under the declared research policy.

Density audit: `research_artifacts/nq_default_spread_orderflow_risk_premium_density_audit_20260623.md`
