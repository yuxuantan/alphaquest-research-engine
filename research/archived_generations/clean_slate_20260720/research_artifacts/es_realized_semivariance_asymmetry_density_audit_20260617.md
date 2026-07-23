# ES Realized Semivariance Asymmetry Density Audit - 2026-06-17

Decision: PROCEED TO TEST.

This audit used only local ES Sierra RTH bars and the derived lagged
semivariance feature CSV. It did not inspect PnL, trade outcomes, equity curves,
or parameter performance.

## Data

- Source bars: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Feature builder: `tools/build_es_realized_semivariance_features.py`
- Feature CSV: `data/external/es_realized_semivariance_features_20110103_20260609.csv`
- Feature rows: `3817`
- Valid rank rows: `3755`
- Period: `2011-01-03` to `2026-06-09`
- Approximate years: `15.430527036276523`

Every tradable feature is shifted one completed RTH session before use.

## Signal Density

Counts below are approximate eligible sessions before performance testing. Each
variant can emit at most one trade per qualifying session.

| Variant | Rank Column | Mode | Threshold | Signals | Signals/Year |
| --- | --- | --- | ---: | ---: | ---: |
| `high_1d_badvol_rebound_long_1000` | `downside1_rank_252` | high tail | 0.25 | 919 | 59.55726579134138 |
| `high_1d_badvol_rebound_long_1000` | `downside1_rank_252` | high tail | 0.35 | 1284 | 83.21167494677076 |
| `high_1d_badvol_rebound_long_1000` | `downside1_rank_252` | high tail | 0.45 | 1622 | 105.11630589070263 |
| `high_1d_badvol_continuation_short_1030` | `downside1_rank_252` | high tail | 0.25 | 919 | 59.55726579134138 |
| `high_1d_badvol_continuation_short_1030` | `downside1_rank_252` | high tail | 0.35 | 1284 | 83.21167494677076 |
| `high_1d_badvol_continuation_short_1030` | `downside1_rank_252` | high tail | 0.45 | 1622 | 105.11630589070263 |
| `high_downside_share_rebound_long_1130` | `downside_share1_rank_252` | high tail | 0.25 | 968 | 62.73278921220724 |
| `high_downside_share_rebound_long_1130` | `downside_share1_rank_252` | high tail | 0.35 | 1331 | 86.25758516678495 |
| `high_downside_share_rebound_long_1130` | `downside_share1_rank_252` | high tail | 0.45 | 1714 | 111.07851312987935 |
| `high_goodvol_fade_short_1200` | `upside1_rank_252` | high tail | 0.25 | 932 | 60.399751596877216 |
| `high_goodvol_fade_short_1200` | `upside1_rank_252` | high tail | 0.35 | 1284 | 83.21167494677076 |
| `high_goodvol_fade_short_1200` | `upside1_rank_252` | high tail | 0.45 | 1630 | 105.6347586941093 |
| `two_sided_5d_bad_good_balance_1330` | `semivar_balance5_rank_252` | two-sided tail | 0.25 | 1910 | 123.7806068133428 |
| `two_sided_5d_bad_good_balance_1330` | `semivar_balance5_rank_252` | two-sided tail | 0.35 | 2672 | 173.16323633782824 |
| `two_sided_5d_bad_good_balance_1330` | `semivar_balance5_rank_252` | two-sided tail | 0.45 | 3381 | 219.1111160397445 |

## Conclusion

All five variant shapes have plausible density above the 50 trades/year
methodology threshold across the declared threshold grid. Proceeding to staged
testing is allowed.
