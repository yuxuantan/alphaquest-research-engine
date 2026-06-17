# ES Realized Semivariance Asymmetry - Rescue Attempt 1

Date: 2026-06-17

Decision: FAIL.

## Scope

Campaign: `es_realized_semivariance_asymmetry`

Data scope: local Sierra ES RTH 1-minute bars plus derived lagged realized
semivariance features. No paid data was downloaded.

The campaign tested prior-session bad-vs-good realized volatility state using
lagged downside semivariance, upside semivariance, downside share, and
bad-minus-good semivariance balance. All tradable features were shifted one
completed RTH session before use.

## Rescue Rule

Each failed original variant received exactly one rescue run. The rescue changed
only the semivariance rank threshold, stop, and target numeric parameter spaces.

Unchanged across rescue:

- `realized_semivariance_asymmetry` entry module
- `percent_from_entry` stop module
- `fixed_r` target module
- feature CSV and one-session lag rule
- variant direction mode, entry time, rank column, and value column
- 1-minute timeframe and Sierra RTH data window
- commission, slippage, tick size, point value, fill rules, session rules, prop rules, and staged validation gates

## Results

All five originals failed `limited_core_grid_test`. Four rescues failed
`limited_core_grid_test`. One rescue passed core and limited monkey, then failed
`walk_forward_analysis`.

| Variant | Run | Terminal Stage | Profitable Combos | Benchmark Combos | Top Net | Top PF | Top Trades/Year | WFA PF | WFA MAR |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `high_1d_badvol_rebound_long_1000` | `run1` | `limited_core_grid_test` | 0/27 | 0 | -440.0 | 0.9628926839553026 | 83.65791337007049 |  |  |
| `high_1d_badvol_rebound_long_1000` | `rescue1` | `limited_core_grid_test` | 5/27 | 0 | 1552.5 | 1.2093023255813953 | 125.52744630071598 |  |  |
| `high_1d_badvol_continuation_short_1030` | `run1` | `limited_core_grid_test` | 6/27 | 0 | 2302.5 | 1.1168336927565647 | 109.55528834774047 |  |  |
| `high_1d_badvol_continuation_short_1030` | `rescue1` | `walk_forward_analysis` | 20/27 | 3 | 5526.25 | 1.3376355582709638 | 92.12618330379841 | 0.6356926570779712 | -0.7825314922408811 |
| `high_downside_share_rebound_long_1130` | `run1` | `limited_core_grid_test` | 1/27 | 0 | 2.5 | 1.0003529827038475 | 71.40731261996535 |  |  |
| `high_downside_share_rebound_long_1130` | `rescue1` | `limited_core_grid_test` | 2/27 | 0 | 555.0 | 1.0958135520069054 | 61.13594845365683 |  |  |
| `high_goodvol_fade_short_1200` | `run1` | `limited_core_grid_test` | 2/27 | 0 | 1105.0 | 1.1070477113102446 | 81.13736173564841 |  |  |
| `high_goodvol_fade_short_1200` | `rescue1` | `limited_core_grid_test` | 10/27 | 0 | 2810.0 | 1.373794479547722 | 133.72474624005008 |  |  |
| `two_sided_5d_bad_good_balance_1330` | `run1` | `limited_core_grid_test` | 0/27 | 0 | -3725.0 | 0.7436779631859625 | 143.28367967396397 |  |  |
| `two_sided_5d_bad_good_balance_1330` | `rescue1` | `limited_core_grid_test` | 0/27 | 0 | -1503.125 | 0.7642156862745098 | 86.76603439797263 |  |  |

The WFA-reaching rescue failed with `early_exit=true`; its stitched OOS after
the first window had net `-9625.0`, PF `0.6356926570779712`, MAR
`-0.7825314922408811`, trades/year `119.6389788870296`, and expectancy R
`-0.24698221123551944`.

## Artifacts

- Aggregate summary: `backtest-campaigns/es_realized_semivariance_asymmetry/campaign_test_summary.json`
- Aggregate CSV: `backtest-campaigns/es_realized_semivariance_asymmetry/campaign_results.csv`
- Source campaign: `campaigns/es_realized_semivariance_asymmetry/campaign.yaml`
- Density audit: `research_artifacts/es_realized_semivariance_asymmetry_density_audit_20260617.md`
- WFA table for the advanced rescue: `backtest-campaigns/es_realized_semivariance_asymmetry/high_1d_badvol_continuation_short_1030/ES/rescue1/walk_forward_analysis/wfa_results.csv`
- WFA OOS trade log for the advanced rescue: `backtest-campaigns/es_realized_semivariance_asymmetry/high_1d_badvol_continuation_short_1030/ES/rescue1/walk_forward_analysis/wfa_oos_trade_log.csv`

## Conclusion

This edge is rejected in active scope. It should not be relaunched under a new
active campaign name without a materially different thesis approved before
testing.
