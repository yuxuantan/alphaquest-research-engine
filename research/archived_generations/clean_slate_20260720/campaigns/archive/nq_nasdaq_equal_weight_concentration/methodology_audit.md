# NQ Nasdaq Equal-Weight Concentration Methodology Audit

Verdict: FAIL.

This campaign passed pre-PnL density testing, then failed staged validation. Three variants failed `limited_core_grid_test`; two variants passed the profitable-combination core breadth gate but had zero benchmark-passing core cells, sparse selected rows, and failed `limited_monkey_test`.

## Lookahead Controls

- QQQ and QQQE daily observations are joined with a one-business-day availability lag.
- Rolling ranks are computed in the daily feature table before the session-level as-of join.
- Entries fire only after a completed NQ RTH bar at the configured time and are entered no earlier than the next bar open.
- No same-day ETF close, final NQ high/low, final VWAP, or post-entry path is used by the signal.

## Duplicate Check

The edge is not a relabel of rejected XLK/SPY technology-relative-strength, semiconductor leadership, broad sector-rotation, sector-dispersion, IWM/QQQ size-rotation, ES/NQ intraday relative-value, or NQ own-momentum campaigns. It specifically tests Nasdaq-100 cap-weight versus equal-weight internal concentration through QQQ/QQQE.

## Artifacts

- Feature builder: `tools/build_nq_nasdaq_equal_weight_features.py`
- Feature CSV: `data/external/nq_nasdaq_equal_weight_features_20110103_20260612.csv`
- Density audit: `research_artifacts/nq_nasdaq_equal_weight_concentration_density_audit_20260701.md`
- Campaign summary: `backtest-campaigns/nq_nasdaq_equal_weight_concentration/campaign_test_summary.json`
- Campaign results: `backtest-campaigns/nq_nasdaq_equal_weight_concentration/campaign_results.csv`

Final decision: FAIL. No variant reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting. No rescue is authorized.
