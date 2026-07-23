# ES/MES same-direction flow confirmation no-go audit - 2026-06-17

Decision: do not queue as the next campaign.

Context: after the longer local Sierra MES cache became available, I checked a
fresh ES/MES idea that would trade ES continuation only when completed ES and
MES signed-flow imbalances confirmed in the same direction.

Data checked:

- `data/cache/orderflow/es_mes_flow_divergence_1m_20190506_20260609_full_rth_ny.csv`
- 685,230 aligned RTH minute bars
- 1,757 sessions
- date range `2019-05-06` through `2026-06-09`

This is not the same mechanic as the failed ES/MES divergence-reversion campaign
or the failed MES participation-crowding fade campaign. However, it overlaps the
active failed own-ES signed-flow persistence family unless MES confirmation is a
core predeclared condition.

Density check at realistic dual-confirmation thresholds:

| proposed variant | signal time | window | side | threshold | min return ticks | signals/year |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| morning_15m_dual_buy_long_1000 | 09:59 | 15 | long | 0.05 | 2 | 14.9 |
| morning_15m_dual_sell_short_1000 | 09:59 | 15 | short | 0.05 | 2 | 13.1 |
| late_morning_30m_dual_buy_long_1130 | 11:29 | 30 | long | 0.05 | 2 | 10.0 |
| late_morning_30m_dual_sell_short_1130 | 11:29 | 30 | short | 0.05 | 2 | 7.2 |
| afternoon_60m_dual_flow_two_sided_1400 | 13:59 | 60 | two-sided | 0.05 | 2 | 11.1 |

Conclusion: the same-direction ES/MES confirmation idea is too sparse at
thresholds that would plausibly indicate real confirmation. Lowering thresholds
enough to force density would make the MES condition weak and more likely a
renamed own-ES signed-flow persistence campaign. Do not launch it under the
current 50 trades/year rule.
