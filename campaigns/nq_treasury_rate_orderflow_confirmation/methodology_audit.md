# nq_treasury_rate_orderflow_confirmation Methodology Audit

Decision: FAIL.

This campaign was authored as an NQ transfer of the ES Treasury-rate/orderflow composite before NQ PnL inspection.
It was eligible as nonduplicate because the already-failed `nq_treasury_rate_shock_intraday` campaign traded lagged Treasury state at fixed bars, while this campaign required same-session completed NQ price movement and cumulative aggregate orderflow confirmation.

No-lookahead controls:
- Treasury features use the latest observation strictly before the NQ session date.
- Entry decisions use completed 5-minute NQ RTH bars only.
- Fills would occur no earlier than the next bar if staged testing had been reached.
- No final session high/low, VWAP, future Treasury value, or post-entry orderflow is used.

Pre-PnL density result:
- Detail: `research_artifacts/nq_treasury_rate_orderflow_confirmation_density_audit_20260630.csv`
- Summary: `research_artifacts/nq_treasury_rate_orderflow_confirmation_density_summary_20260630.csv`
- Result: 19/45 entry rows passed; 0/5 variants passed all declared rows.

Conclusion: reject before staged PnL. No rescue is authorized.
