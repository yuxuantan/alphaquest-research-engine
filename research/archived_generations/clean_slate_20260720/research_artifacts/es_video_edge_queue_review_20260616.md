# Video Edge Queue Review - 2026-06-16

Decision: no immediate queued ES campaign from this list.

Last refreshed: 2026-06-17.

Scope: active-only duplicate check; archived tests ignored. This review only evaluates whether the listed concepts are usable as next ES futures campaigns under the current methodology and local/free-data constraints. It does not treat broad market validity as enough; the concept must translate into a point-in-time, ES-specific, dense-enough campaign without paid data and without duplicating an active failed edge.

| Concept | ES campaign eligibility | Reason |
| --- | --- | --- |
| Earnings surprise drift / PEAD | Not queued | Equity single-name earnings drift is not directly an ES intraday futures edge. A valid ES version would require point-in-time aggregate index-constituent earnings surprise data and a predeclared breadth/weighting model. Not locally available and not queued. |
| Initial Balance / Opening Range Breakout | Usable concept, not queued | ES-relevant and likely dense enough, but active failed `es_range_compression_breakout` and prior opening-range/range-compression work already cover opening-range breakout mechanics. A pure IB campaign would need a materially distinct predeclared mechanism before it avoids duplicate-edge status. |
| Politician tracking / asymmetrical information | Not queued | Congressional trade disclosures are delayed, equity/security-specific, and not a direct ES intraday futures edge. It also requires point-in-time disclosure ingestion and mapping to ES exposure. |
| Option premium harvesting / volatility risk premium | Usable concept, not queued | The broad volatility-risk-premium family is already active and failed in `es_variance_risk_premium_intraday`, `es_vvix_tail_risk_intraday`, `es_vix_expiration_pressure`, and the latest `es_cboe_put_call_sentiment_intraday` proxy. Option-selling itself would require options data, margin, exercise/assignment, and expiration mechanics outside this ES futures backtest engine. |
| Blockchain intelligence / smart DCA | Not queued | Crypto on-chain allocation timing is not an ES futures edge and does not fit the current ES intraday methodology. |

Current status:
- The Treasury-rate, OFR financial-stress, VVIX tail-risk, EPU policy-uncertainty, consumer-sentiment, Cboe put/call, and oil price-shock spillover campaigns that followed this review have since been completed and failed under the staged methodology.
- Active sweep after the latest completed campaign found 45 active campaigns, 225 source variants, 225 rescue configs, 468 raw variant-level reports, and 0 pass-like reports.
- This review still queues none of the five video-listed concepts as the next ES campaign.

Queued after current campaign:
- None from this video list.

Practical next action:
- Do not relaunch the listed edges unless a materially new, point-in-time, ES-specific, dense data source and non-duplicate mechanic is defined before testing.
- Continue the ES search with a different non-duplicate, dense, public/local-data edge, or with an explicitly approved external-data branch.
