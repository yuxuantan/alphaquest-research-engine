# NQ BTC Crypto Risk Sentiment Methodology Audit

Verdict: FAIL.

The campaign passed the pre-PnL density screen, but staged validation failed closed. Four variants failed `limited_core_grid_test`; `btc_volatility_riskoff_short_1330` passed limited core and then failed `limited_monkey_test`.

## Lookahead Controls

- BTC-USD daily observations are joined with a one-calendar-day availability lag.
- Entries fire only after a completed NQ RTH bar at the configured time.
- No same-day BTC close, final NQ high/low, final VWAP, or post-entry path is used.

## Duplicate Check

The edge is not a relabel of small-cap rotation, European/Tokyo equity spillover, FX/oil shock, VIX/VVIX/variance state, ES/NQ relative value, or NQ own-momentum campaigns. It specifically tests crypto risk sentiment through lagged BTC return and volatility ranks.

## Staged Result

- Valid staged evidence: `run1`.
- Terminal gate: `limited_monkey_test`.
- `btc_volatility_riskoff_short_1330` failed monkey robustness with core-vs-monkey net-profit beat rate 0.73475 and max-drawdown beat rate 0.676875, both below the 0.90 requirement.
- No branch reached WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

## Artifacts

- Feature builder: `tools/build_nq_btc_crypto_risk_sentiment_features.py`
- Feature CSV: `data/external/nq_btc_crypto_risk_sentiment_features_20150115_20260612.csv`
- Density audit: `research_artifacts/nq_btc_crypto_risk_sentiment_density_audit_20260701.md`
- Campaign results: `backtest-campaigns/nq_btc_crypto_risk_sentiment/campaign_results.csv`
- Campaign summary: `backtest-campaigns/nq_btc_crypto_risk_sentiment/campaign_test_summary.json`
