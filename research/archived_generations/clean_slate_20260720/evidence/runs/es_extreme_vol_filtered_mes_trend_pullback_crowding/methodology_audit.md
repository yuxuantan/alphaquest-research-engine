# Methodology Audit: es_extreme_vol_filtered_mes_trend_pullback_crowding

Verdict: FAIL

Pre-test controls:
- Five variants were declared before testing in `campaigns/es_extreme_vol_filtered_mes_trend_pullback_crowding/campaign.yaml`.
- The campaign used a bounded MES trend-pullback crowding mechanic plus a pre-entry lagged-volatility veto.
- Parameter grids were declared in the variant configs before staged testing; rescue attempts were recorded under `rescue1` where present.
- The volatility filters are prior-session lagged features and do not use current-session realized volatility or future high/low data.
- Entries use completed one-minute bars and next-bar execution; no overnight exposure is allowed by config.

Result:
- No run passed the full staged pipeline.
- Three original/rescue runs reached `simulated_incubation_core` and failed there; the remaining runs failed `limited_monkey_test`.
- No run reached acceptance OOS or candidate reporting.
- Rescue attempts did not improve the campaign to a pass; several rescues failed earlier at monkey testing.

Failure interpretation:
The edge is rejected as tested. The strongest-looking train/WFA path was not robust in simulated incubation. For example, `exclude_extreme_absret5_trade_morning_1030/run1` selected profitable train parameters but the incubation OOS core produced net -13517.5, PF 0.6568509233991242, MAR -0.7864245825477231, and only 23.1% positive months. This is a hard fail, not a candidate strategy.
