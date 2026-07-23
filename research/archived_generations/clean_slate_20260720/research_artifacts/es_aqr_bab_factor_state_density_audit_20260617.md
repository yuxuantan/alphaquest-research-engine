# ES AQR BAB Factor State Density Audit - 2026-06-17

Scope: pre-test signal-density check only. No PnL, fills, or trade outcomes are inspected here.

Feature file: `data/external/es_aqr_bab_features_20110103_20260609.csv`
Sessions: 3817 from 2011-01-03 to 2026-06-09 (~15.43 years).
Availability rule: latest AQR BAB observation at least 45 calendar days before the ES session.

| Variant | Rank column | Thresholds | Signal counts / year | Density conclusion |
|---|---|---:|---:|---|
| `low_bab_daily_rebound_long_0935` | `bab_usa_return_rank_252` | [0.25, 0.3, 0.35] | 0.25: 902 / 58.5, 0.3: 1085 / 70.3, 0.35: 1254 / 81.3 | PASS density gate |
| `low_bab_21d_rebound_long_1000` | `bab_usa_sum21_rank_252` | [0.25, 0.3, 0.35] | 0.25: 935 / 60.6, 0.3: 1096 / 71.0, 0.35: 1332 / 86.3 | PASS density gate |
| `low_bab_63d_rebound_long_1030` | `bab_usa_sum63_rank_252` | [0.25, 0.3, 0.35] | 0.25: 940 / 60.9, 0.3: 1108 / 71.8, 0.35: 1308 / 84.8 | PASS density gate |
| `low_bab_z63_rebound_long_1100` | `bab_usa_z63_rank_252` | [0.25, 0.3, 0.35] | 0.25: 922 / 59.8, 0.3: 1072 / 69.5, 0.35: 1262 / 81.8 | PASS density gate |
| `bab_63d_extreme_two_sided_1330` | `bab_usa_sum63_rank_252` | [0.15, 0.2, 0.25] | 0.15: 1280 / 83.0, 0.2: 1618 / 104.9, 0.25: 1968 / 127.5 | PASS density gate |

Decision: proceed to preflight. The campaign is dense enough to test without knowingly pursuing a <50 trades/year concept.
