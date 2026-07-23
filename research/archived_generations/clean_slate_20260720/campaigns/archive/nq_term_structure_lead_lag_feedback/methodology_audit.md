# NQ Front-vs-Next Contract Term-Structure Lead-Lag Feedback Methodology Audit

Verdict: FAIL.

The campaign was rejected before staged PnL. The declared five-variant NQ front-vs-next-contract spread-feedback grid produced 0 passing density rows out of 45. The best row produced 47 total signals, 2.9814 full-history signals per year, 5 limited-window signals, and 10 signals in the latest 40 eligible sessions. This is below the predeclared density gate of at least 80 total signals, 10 full-period signals/year, and 10 limited-period signals/year.

No PnL was inspected. No parameter rescue is authorized.

## Source And Edge

Source campaign: `es_term_structure_lead_lag_feedback`.

Primary sources: Li, Chen, and Liu (2025) on calendar-spread lead-lag in stock-index futures; Michael, Cucuringu, and Howison (2024) on connected ES futures structures; Huth and Abergel (2014) on high-frequency lead-lag relationships.

Local expression: one-minute NQ RTH front-contract bars aligned with the next explicit quarterly NQ contract. Signals use completed front/deferred return gaps at fixed times and would trade only the front NQ contract.

## Lookahead Controls

- Front contract selection uses the explicit roll-calendar front cache.
- Deferred contract selection uses the next explicit roll-calendar contract.
- Rolling feature columns use completed current-or-prior one-minute bars only.
- The signal timestamp is the configured bar close; execution would be next-bar or later.
- No future session high, low, VWAP, final range, volume profile, same-day volume-based roll choice, or post-entry path is used.

## Duplicate Check

This was allowed to reach density screening because it tests same-underlying NQ front-vs-next maturity-basis dislocation. It is not the same edge as NQ/ES cross-index lead-lag, NQ prior-level reactions, opening-range behavior, liquidity/FVG campaigns, or quarterly-expiration calendar pressure.

## Data Gate

- Derived cache: `data/cache/orderflow/nq_term_structure_lead_lag_1m_20100607_20260529_full_rth_ny.parquet`
- Validation: `data/cache/orderflow/nq_term_structure_lead_lag_1m_20100607_20260529_full_rth_ny.validation.json`
- Complete RTH sessions: 164
- Rows: 63960
- Cache validation: `{'deferred_contracts': 40, 'duplicate_timestamps': 0, 'front_contracts': 40, 'invalid_ohlc_rows': 0, 'missing_session_segments': 0}`

## Artifacts

- Density audit: `research_artifacts/nq_term_structure_lead_lag_feedback_density_audit_20260630.md`
- Density CSV: `research_artifacts/nq_term_structure_lead_lag_feedback_density_audit_20260630.csv`
- Summary CSV: `research_artifacts/nq_term_structure_lead_lag_feedback_density_summary_20260630.csv`
- Backtest summary placeholder: `backtest-campaigns/nq_term_structure_lead_lag_feedback/campaign_test_summary.json`

Final decision: FAIL.
