# nq_real_yield_breakeven_state density audit

Verdict: PASS.

This is a pre-PnL density audit. It counts only signal availability from lagged real-yield/breakeven feature rows whose observation date is strictly before the NQ session date. It does not inspect stops, targets, trade outcomes, WFA, Monte Carlo, or prop-rule results.

- Detail CSV: `research_artifacts/nq_real_yield_breakeven_state_density_audit_20260630.csv`
- Summary CSV: `research_artifacts/nq_real_yield_breakeven_state_density_summary_20260630.csv`
- Full-history threshold: >= 50 signals/year
- Limited-core window: 2011-02-22 through 2012-09-07, threshold >= 50 signals/year
- Latest-252 threshold: >= 50 signals
- Density rows passing: 15/15
- Variants passing all declared rows: 5/5

| variant | rows | pass rows | min full/year | min limited/year | min latest 252 | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| breakeven_1d_up_long_1000 | 3 | 3 | 87.83 | 84.91 | 86 | PASS |
| breakeven_5d_down_short_1130 | 3 | 3 | 87.11 | 83.55 | 87 | PASS |
| real_yield_1d_down_long_1000 | 3 | 3 | 87.11 | 83.55 | 84 | PASS |
| real_yield_1d_up_short_1000 | 3 | 3 | 87.90 | 81.51 | 86 | PASS |
| real_yield_5d_up_short_1130 | 3 | 3 | 88.82 | 80.83 | 89 | PASS |

Conclusion: density is sufficient to proceed to preflight and staged validation. This is not evidence of profitability.
