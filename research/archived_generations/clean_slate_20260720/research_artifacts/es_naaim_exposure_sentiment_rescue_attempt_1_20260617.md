# ES NAAIM Exposure Sentiment Rescue Attempt 1 - 2026-06-17

Decision: FAIL.

## Scope

Campaign: `es_naaim_exposure_sentiment`

The rescue preserved the core strategy mechanic:

- Same entry module: `naaim_exposure_sentiment`
- Same stop module: `percent_from_entry`
- Same target module: `fixed_r`
- Same NAAIM two-business-day availability rule
- Same setup mode and entry time per variant
- Same data, costs, slippage, tick size, point value, sessions, prop rules, and validation gates

Allowed rescue changes:

- Adjusted only stop and target parameter spaces to a tighter intraday risk envelope

## Original Outcome

All five originals failed `limited_core_grid_test`.

| Variant | Profitable combo rate | Top net | Top PF | Top trades |
|---|---:|---:|---:|---:|
| `level_median_contrarian_1000` | 0.0 | -1587.50 | 0.753206 | 80 |
| `level_rank_contrarian_1030` | 0.0 | -2525.00 | 0.736155 | 80 |
| `weekly_change_contrarian_1130` | 0.0 | -2537.50 | 0.670455 | 80 |
| `zscore_sign_contrarian_1200` | 0.0 | -1925.00 | 0.700389 | 80 |
| `ma_distance_contrarian_1400` | 0.0 | -1287.50 | 0.720109 | 80 |

## Rescue Outcome

All five rescues failed `limited_core_grid_test`.

| Variant | Profitable combo rate | Top net | Top PF | Top trades |
|---|---:|---:|---:|---:|
| `level_median_contrarian_1000` | 0.0 | -1687.50 | 0.610727 | 80 |
| `level_rank_contrarian_1030` | 0.0 | -2587.50 | 0.402080 | 80 |
| `weekly_change_contrarian_1130` | 0.0 | -2087.50 | 0.303586 | 80 |
| `zscore_sign_contrarian_1200` | 0.0 | -2750.00 | 0.447514 | 80 |
| `ma_distance_contrarian_1400` | 0.0 | -1525.00 | 0.635167 | 80 |

## Artifacts

- `backtest-campaigns/es_naaim_exposure_sentiment/campaign_test_summary.json`
- `backtest-campaigns/es_naaim_exposure_sentiment/campaign_results.csv`
- `backtest-campaigns/es_naaim_exposure_sentiment/wfa_table.csv`
- `backtest-campaigns/es_naaim_exposure_sentiment/monte_carlo_summary.json`
- `research_artifacts/es_naaim_exposure_sentiment_density_audit_20260617.md`

## Final Decision

FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.
