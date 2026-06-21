# ES Market Structure Pivot Composite Queue

CSV: `research_artifacts/es_market_structure_pivot_composite_queue_20260620.csv`

Selection fixed after the standalone pivot campaign failed and before any composite PnL testing. These are not rescues of the failed standalone pivot campaign; each planned composite must be authored as its own primary-edge-plus-fixed-pivot-filter campaign and pass the same staged benchmarks.

## Status

| rank | new_campaign_id | status | decision | outcome |
| --- | --- | --- | --- | --- |
| 1 | `es_pivot_filtered_mes_participation_crowding_reversion` | completed | FAIL | One original and one stop-widen rescue reached limited monkey; both failed monkey robustness. No WFA. |
| 2 | `es_pivot_filtered_vwap_pullback_continuation` | completed | FAIL | Originals and one stop-widen rescue per failed variant all failed limited core. |
| 3 | `es_pivot_filtered_prior_value_area_acceptance` | completed | FAIL | Originals and one stop-widen rescue per failed variant all failed limited core. |
| 4 | `es_pivot_filtered_spx_0dte_pressure` | rejected pre-PnL | FAIL | Fixed pivot filter left fewer than 50 signals/year across required windows. |
| 5 | `es_pivot_filtered_opening_range_orderflow_breakout` | rejected pre-PnL | FAIL | Only 1/5 variants kept all declared entry parameter corners above 50 signals/year after pivot filtering. |

Final queue decision: FAIL. The completed pivot market-structure filter did not produce a candidate strategy as a standalone edge or as a fixed direction filter on the five selected existing campaigns.

| rank | new_campaign_id | base_campaign_id | base_variant_id | rationale |
| --- | --- | --- | --- | --- |
| 1 | `es_pivot_filtered_mes_participation_crowding_reversion` | `es_mes_participation_crowding_reversion` | `morning_notional_down_reversal_long_1030` | Strongest partial core evidence among MES crowding variants; pivot uptrend bias is economically consistent with fading a crowded morning selloff only when broader completed structure remains up. |
| 2 | `es_pivot_filtered_vwap_pullback_continuation` | `es_vwap_pullback_continuation` | `midday_trend_reclaim_two_sided` | Dense price-action continuation edge with prior partial core strength; pivot bias is a natural higher-structure confirmation for VWAP reclaim continuation. |
| 3 | `es_pivot_filtered_prior_value_area_acceptance` | `es_prior_value_area_orderflow_acceptance` | `morning_signed_vah_acceptance_long` | Prior value-area acceptance has strong limited-core partial evidence; pivot uptrend bias is consistent with accepting above prior value only when completed structure agrees. |
| 4 | `es_pivot_filtered_spx_0dte_pressure` | `es_spx_0dte_expiration_pressure` | `full_week_late_move_continuation_1430` | 0DTE late-move continuation had high core profitability in rescue/stop-widen artifacts and enough post-2022 signal density; pivot bias can filter continuation to days where ES structure agrees with hedging feedback direction. |
| 5 | `es_pivot_filtered_opening_range_orderflow_breakout` | `es_opening_range_orderflow_breakout` | `or30_large20_flow_breakout_1100` | Opening-range/orderflow breakout is a dense price-action/orderflow campaign even though standalone results were weak; pivot bias is a plausible predeclared direction filter for false-breakout reduction. It is ranked lower because prior core evidence was poor. |
