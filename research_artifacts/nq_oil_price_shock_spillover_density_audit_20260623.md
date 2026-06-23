# Pre-PnL Density Audit: nq_oil_price_shock_spillover

Date: 2026-06-23

Verdict: PASS.

This audit was run before any NQ PnL inspection. It checks the predeclared ES parameter-space rescue entry thresholds on the NQ session-mapped oil feature file.

- Feature file: `data/external/nq_oil_price_shock_features_20110103_20260612.csv`
- Minimum full-history signal density required: 50 signals/year.
- Minimum latest-252-session signal count required: 50.
- No density-only trim was needed.

## Variant Summary

| variant | min full signals/year | min latest252 signals | verdict |
|---|---:|---:|---|
| brent_up_global_shock_short_1130 | 61.7926 | 80 | PASS |
| brent_wti_spread_widen_short_1330 | 59.4608 | 70 | PASS |
| oil_volatility_stress_short_1200 | 63.3471 | 83 | PASS |
| wti_down_relief_long_1000 | 60.4972 | 57 | PASS |
| wti_up_risk_off_short_1030 | 61.6631 | 72 | PASS |

## Threshold Detail

| variant | entry param | threshold | driver | full/year | latest252 | verdict |
|---|---|---:|---|---:|---:|---|
| brent_up_global_shock_short_1130 | entry.params.oil_return_rank_min | 0.65 | brent_return_1d_rank_252 | 86.1469 | 96 | PASS |
| brent_up_global_shock_short_1130 | entry.params.oil_return_rank_min | 0.7 | brent_return_1d_rank_252 | 74.3584 | 88 | PASS |
| brent_up_global_shock_short_1130 | entry.params.oil_return_rank_min | 0.75 | brent_return_1d_rank_252 | 61.7926 | 80 | PASS |
| brent_wti_spread_widen_short_1330 | entry.params.spread_change_rank_min | 0.65 | brent_wti_spread_change_1d_rank_252 | 84.7219 | 91 | PASS |
| brent_wti_spread_widen_short_1330 | entry.params.spread_change_rank_min | 0.7 | brent_wti_spread_change_1d_rank_252 | 71.6380 | 79 | PASS |
| brent_wti_spread_widen_short_1330 | entry.params.spread_change_rank_min | 0.75 | brent_wti_spread_change_1d_rank_252 | 59.4608 | 70 | PASS |
| oil_volatility_stress_short_1200 | entry.params.oil_abs_rank_min | 0.65 | oil_abs_return_1d_rank_252 | 87.4424 | 108 | PASS |
| oil_volatility_stress_short_1200 | entry.params.oil_abs_rank_min | 0.7 | oil_abs_return_1d_rank_252 | 74.2289 | 95 | PASS |
| oil_volatility_stress_short_1200 | entry.params.oil_abs_rank_min | 0.75 | oil_abs_return_1d_rank_252 | 63.3471 | 83 | PASS |
| wti_down_relief_long_1000 | entry.params.oil_return_rank_max | 0.35 | wti_return_1d_rank_252 | 84.8515 | 83 | PASS |
| wti_down_relief_long_1000 | entry.params.oil_return_rank_max | 0.3 | wti_return_1d_rank_252 | 72.8039 | 71 | PASS |
| wti_down_relief_long_1000 | entry.params.oil_return_rank_max | 0.25 | wti_return_1d_rank_252 | 60.4972 | 57 | PASS |
| wti_up_risk_off_short_1030 | entry.params.oil_return_rank_min | 0.65 | wti_return_1d_rank_252 | 84.9810 | 91 | PASS |
| wti_up_risk_off_short_1030 | entry.params.oil_return_rank_min | 0.7 | wti_return_1d_rank_252 | 73.1277 | 83 | PASS |
| wti_up_risk_off_short_1030 | entry.params.oil_return_rank_min | 0.75 | wti_return_1d_rank_252 | 61.6631 | 72 | PASS |
