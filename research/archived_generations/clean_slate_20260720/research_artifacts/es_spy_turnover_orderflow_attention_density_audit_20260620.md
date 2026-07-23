# ES SPY Turnover Orderflow Attention Density Audit - 2026-06-20

Data sources: local Sierra ES RTH aggregate-orderflow cache and existing local free Yahoo SPY daily CSV. No paid data was downloaded.

Availability rule: each ES session uses the latest SPY daily adjusted close and volume strictly before the ES session date. ES confirmation uses completed 5-minute RTH bars only, with intended next-bar entry.

Density gate: selected variants must plausibly clear 50 trades/year before any PnL testing. Counts below use fixed pre-test settings: attention rank threshold 0.65, minimum ES move 2 ticks, minimum signed-flow imbalance 0.0, max one trade per day, and signal decisions at 10:00, 10:30, 11:30, 12:30, 14:30, and 15:30 ET.

| variant | feature spec | full signals | full/year | limited-core/year |
|---|---:|---:|---:|---:|
| spy_1d_volume_attention_continuation_1530 | vol20_1d_full | 855 | 55.41 | 54.59 |
| spy_1d_absret_attention_continuation_1530 | abs1_1d_full | 876 | 56.77 | 63.69 |
| spy_3d_volume_attention_continuation_1530 | vol63_3d_full | 877 | 56.84 | 54.59 |
| spy_3d_absret_attention_continuation_1530 | abs3_3d_full | 849 | 55.02 | 55.89 |
| spy_5d_volume_attention_continuation_1530 | vol63_5d_full | 882 | 57.16 | 58.49 |

Rejected drafts: morning-only, midday-only, stricter signed-flow imbalance, and single 10:00 decision variants were rejected when the full-history density fell below 50 signals/year or depended on only the loosest attention thresholds.

Decision: PASS pre-PnL density gate for the five selected full-day variants.
