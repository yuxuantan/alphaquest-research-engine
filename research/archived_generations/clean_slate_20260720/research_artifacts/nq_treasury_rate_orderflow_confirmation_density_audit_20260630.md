# nq_treasury_rate_orderflow_confirmation density audit

Verdict: FAIL.

This is a pre-PnL density audit. It counts only signal availability from completed 5-minute NQ RTH bars, lagged Treasury features whose observation date is strictly before the NQ session date, and the declared entry-parameter grid. It does not inspect stops, targets, trade outcomes, equity curves, WFA, Monte Carlo, or prop-rule outcomes.

- Detail CSV: `research_artifacts/nq_treasury_rate_orderflow_confirmation_density_audit_20260630.csv`
- Summary CSV: `research_artifacts/nq_treasury_rate_orderflow_confirmation_density_summary_20260630.csv`
- Full-history threshold: >= 50 signals/year
- Limited-core window: 2011-02-22 through 2012-09-07, threshold >= 50 signals/year
- Latest-252 threshold: >= 50 signals
- Density rows passing: 19/45
- Variants passing all declared rows: 0/5

| variant | rows | pass rows | min full/year | min limited/year | min latest 252 | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| curve_1d_signed_rate_confirmation_1530 | 9 | 3 | 12.23 | 29.21 | 5 | FAIL |
| teny_1d_large10_rate_confirmation_1530 | 9 | 8 | 58.36 | 45.51 | 59 | FAIL |
| teny_1d_signed_rate_confirmation_1530 | 9 | 3 | 12.09 | 23.77 | 4 | FAIL |
| teny_5d_signed_rate_confirmation_1530 | 9 | 3 | 12.09 | 27.85 | 3 | FAIL |
| twoy_1d_signed_rate_confirmation_1530 | 9 | 2 | 13.55 | 19.02 | 8 | FAIL |

Conclusion: reject before staged PnL unless the user explicitly authorizes a different edge or a rescue. The declared family does not clear the pre-performance opportunity-count gate.
