# NQ Tech Relative Strength Density Audit

Generated on 2026-06-22 before any NQ PnL testing for `nq_tech_relative_strength_intraday`.

Feature file: `data/external/nq_tech_relative_strength_features_20110103_20260612.csv`

Availability rule: each NQ session uses only XLK and SPY observations available on or before `session_date - 1 business day`.

| Variant | Driver | Threshold grid | Signals range | Signals/year range |
|---|---|---:|---:|---:|
| tech_1d_strength_long_1000 | xlk_minus_spy_1d_rank_252 >= rank_min | 0.55, 0.60, 0.65 | 1389-1745 | 89.97-113.03 |
| tech_5d_strength_long_1030 | xlk_minus_spy_5d_rank_252 >= rank_min | 0.55, 0.60, 0.65 | 1398-1755 | 90.55-113.68 |
| tech_1d_weakness_short_1000 | xlk_minus_spy_1d_rank_252 <= rank_max | 0.45, 0.40, 0.35 | 1334-1704 | 86.41-110.37 |
| tech_5d_weakness_short_1130 | xlk_minus_spy_5d_rank_252 <= rank_max | 0.45, 0.40, 0.35 | 1315-1671 | 85.18-108.23 |
| tech_attention_strength_long_1330 | attention rank >= rank_min and volume rank >= volume_rank_min | 0.55-0.65 x 0.55-0.65 | 543-790 | 35.17-51.17 |

Decision: approve for authoring. Thresholds are selected from signal density only; no PnL or returns were inspected during this screen.
