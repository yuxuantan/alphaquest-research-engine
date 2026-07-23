# ES Market Structure Pivot Filter Final Report

Date: 2026-06-20

Decision: FAIL

This report covers the completed swing-pivot market-structure idea requested as:

- A standalone ES campaign.
- A fixed direction filter combined with five selected existing ES campaigns.

The filter used completed OHLCV swing pivots only after right-side confirmation bars were complete. The tested implementation used 5-minute and 15-minute RTH pivot states; a long bias required HH/HL structure, a short bias required LH/LL structure, and mixed or opposed states blocked trades. Signals still used completed-bar information and staged tests still entered next bar.

## Academic Support Used

- Lo, Mamaysky, and Wang (2000), "Foundations of Technical Analysis": algorithmic local extrema can be formalized and tested rather than hand-labeled.
- Brock, Lakonishok, and LeBaron (1992), "Simple Technical Trading Rules and the Stochastic Properties of Stock Returns": trading-range and trend-following rules can have statistical content, motivating objective tests rather than discretionary pattern claims.
- Moskowitz, Ooi, and Pedersen (2012), "Time Series Momentum": futures markets have documented trend persistence at longer horizons, but this does not guarantee intraday ES pivot-pattern profitability.
- Hurst, Ooi, and Pedersen (2017), "A Century of Evidence on Trend-Following Investing": trend-following context only; the local ES methodology remained the decision authority.

## Standalone Campaign

Campaign: `es_market_structure_pivot_trend_bias`

Outcome: FAIL

All five original variants and all five one-time parameter-space rescues failed `limited_core_grid_test`. No branch reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Primary artifact: `backtest-campaigns/es_market_structure_pivot_trend_bias/campaign_test_summary.json`

## Composite Campaigns

| rank | campaign | decision | result |
|---:|---|---|---|
| 1 | `es_pivot_filtered_mes_participation_crowding_reversion` | FAIL | One original and one stop-widen rescue reached limited monkey; both failed monkey robustness. No WFA. |
| 2 | `es_pivot_filtered_vwap_pullback_continuation` | FAIL | All originals and stop-widen rescues failed limited core. |
| 3 | `es_pivot_filtered_prior_value_area_acceptance` | FAIL | All originals and stop-widen rescues failed limited core. |
| 4 | `es_pivot_filtered_spx_0dte_pressure` | FAIL | Rejected before PnL because pivot filtering left insufficient signal density. |
| 5 | `es_pivot_filtered_opening_range_orderflow_breakout` | FAIL | Rejected before PnL because only one of five ORB variants kept all entry parameter corners above 50 signals/year after pivot filtering. |

## Conclusion

The completed pivot market-structure direction filter is not promoted. It was plausible enough to test because it expresses a known technical-analysis/trend concept using delayed, completed pivots, but the evidence did not survive the methodology:

- As a standalone edge, it failed limited core.
- As a filter, it often reduced trade density too much.
- Where density survived, it did not produce enough profitable and robust parameter neighborhoods after ES costs and slippage.

No `candidate_strategy_report.md` was created because there is no candidate strategy from this idea.
