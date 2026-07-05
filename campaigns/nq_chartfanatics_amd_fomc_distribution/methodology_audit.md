# NQ ChartFanatics AMD FOMC Distribution Methodology Audit

Verdict: FAIL.

The campaign was rejected before staged PnL. The corrected pre-PnL density audit annualized signals over the full NQ RTH history, not only FOMC event sessions. Only 5/45 declared entry-grid rows cleared the sparse-event threshold of at least 5 signals/year, and 0/5 variants passed all declared rows.

No PnL was inspected. No parameter rescue is authorized.

## Source And Edge

Primary source: ChartFanatics AMD Model, Tanja Trades, https://www.chartfanatics.com/strategies/amd-model.

Local expression: scheduled FOMC decision dates only; pre-release accumulation range ending 14:00 ET; completed liquidity sweep; completed displacement through the configured midpoint or opposite edge; next-bar NQ entry; sweep-extreme stop; fixed-R target; same-day flatten.

## Lookahead Controls

- FOMC event dates are scheduled and known before the session.
- No FOMC decision, statement, surprise, press conference, minutes, or post-event content is used.
- The accumulation range is frozen from completed bars before any sweep/displacement signal is counted.
- Entry can occur only after the completed signal bar, at the next bar open.
- No future session high/low, final VWAP, final range, or post-entry orderflow is used.

## Duplicate Check

This was allowed to reach density screening because it is not the same edge as fixed-time FOMC drift, BLS release-day drift, ordinary opening-range failed breakout, RTH liquidity inversion/FVG, or SMT midpoint reversion. It combines scheduled FOMC event context with an AMD sweep/displacement sequence.

## Artifacts

- Density audit: `research_artifacts/nq_chartfanatics_amd_fomc_distribution_density_audit_20260701.md`
- Density CSV: `research_artifacts/nq_chartfanatics_amd_fomc_distribution_density_audit_20260701.csv`
- Summary CSV: `research_artifacts/nq_chartfanatics_amd_fomc_distribution_density_summary_20260701.csv`
- Backtest summary placeholder: `backtest-campaigns/nq_chartfanatics_amd_fomc_distribution/campaign_test_summary.json`
- Results CSV: `backtest-campaigns/nq_chartfanatics_amd_fomc_distribution/campaign_results.csv`

Final decision: FAIL.
