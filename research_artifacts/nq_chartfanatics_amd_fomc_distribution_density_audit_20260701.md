# nq_chartfanatics_amd_fomc_distribution density audit

Verdict: FAIL.

This is a pre-PnL density audit. It counts only scheduled FOMC decision dates and completed NQ RTH bars through each configured signal window. It does not inspect stops, targets, trade outcomes, WFA, Monte Carlo, or prop-rule results.

- Detail CSV: `research_artifacts/nq_chartfanatics_amd_fomc_distribution_density_audit_20260701.csv`
- Summary CSV: `research_artifacts/nq_chartfanatics_amd_fomc_distribution_density_summary_20260701.csv`
- FOMC calendar: `data/external/fomc_scheduled_decision_dates_20110101_20260609.csv`
- NQ bar cache: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Sparse-event threshold: >= 5 signals/year for every declared entry row
- Density rows passing: 5/45
- Variants passing all declared rows: 0/5

| variant | rows | pass rows | min signals/year | min limited/year | min latest 365d | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| fomc_1300_1400_two_sided_midpoint_1530 | 9 | 0 | 4.43 | 2.04 | 4 | FAIL |
| fomc_1330_1400_buyside_bearish_edge_1500 | 9 | 0 | 2.97 | 2.72 | 5 | FAIL |
| fomc_1330_1400_sellside_bullish_edge_1500 | 9 | 0 | 3.50 | 1.36 | 4 | FAIL |
| fomc_1330_1400_two_sided_midpoint_1500 | 9 | 5 | 4.69 | 3.40 | 5 | FAIL |
| fomc_1345_1400_two_sided_edge_1500 | 9 | 0 | 4.16 | 3.40 | 6 | FAIL |

Conclusion: reject before staged PnL. Do not drop sparse variants or loosen thresholds without an explicit rescue authorization.
