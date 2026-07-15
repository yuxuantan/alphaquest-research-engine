# NQ China Tech Risk Sentiment Methodology Audit

Decision before staged PnL: approved for testing after duplicate-edge screening and pre-PnL signal-density audit.

ChartFanatics source gate: `research_artifacts/chartfanatics_remaining_strategy_source_gate_after_nq_jobless_claims_20260701.md` concluded that no additional ChartFanatics ES/NQ campaign should be launched without explicitly relaxing the no-duplicate-edge constraint or accepting currently data-gated intraday VIX/depth/order-book mechanics. This campaign was therefore not presented as a ChartFanatics-derived duplicate; it tests a separate prior-day China ETF risk-sentiment spillover edge.

Duplicate screen: this is not a retest of Nikkei close spillover, European cash-close spillover, semiconductor leadership, copper growth sentiment, small-cap rotation, USDJPY safe-haven, or NQ own-momentum. It uses prior-business-day CQQQ/FXI states relative to QQQ.

Lookahead controls:
- A session dated D may use only CQQQ, FXI, and QQQ daily observations dated no later than one business day before D.
- Rolling ranks are computed on completed daily ETF observations before the NQ session-level join.
- Signals use completed one-minute NQ bars and enter no earlier than the next bar open.
- No same-day ETF return, future NQ high/low, final VWAP, post-entry path, or future China/QQQ observation is used.

Known caveats:
- Yahoo ETF daily history is not an exchange-certified point-in-time dataset and would require vendor verification before any promotion.
- CQQQ/FXI moves may be coincident global risk sentiment rather than a leading NQ signal.
- China policy and idiosyncratic ETF microstructure can dominate broad Nasdaq transmission.
- Same-bar stop/target conflicts remain pessimistic because tick path is not used.

Pre-PnL density:
- Feature builder: `tools/build_nq_china_tech_risk_sentiment_features.py`.
- Feature CSV: `data/external/nq_china_tech_risk_sentiment_features_20110103_20260612.csv`.
- Density audit passed 45/45 declared entry rows: `research_artifacts/nq_china_tech_risk_sentiment_density_audit_20260701.md`.

Post-test decision:
- Decision: FAIL.
- Three variants failed limited_core_grid_test by profitable-iteration breadth.
- Two variants passed core and monkey but failed walk_forward_analysis with early exits and negative stitched OOS metrics.
- No branch reached WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.
- Campaign summary: `backtest-campaigns/nq_china_tech_risk_sentiment/campaign_test_summary.json`.
