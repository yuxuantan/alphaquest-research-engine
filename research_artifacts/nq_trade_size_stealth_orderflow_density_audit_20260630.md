# NQ Trade-Size Stealth Orderflow Density Audit

Date: 2026-06-30

Verdict: PASS pre-PnL density screen.

Method: counted candidate signals only on `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet` using completed 1-minute rolling orderflow windows. No NQ PnL was inspected before this audit.

Density floor: every declared entry-grid row must clear 50 signals/year and maintain a reasonable latest-252-session sample.

| Variant | Min signals/year | Max signals/year | Min latest-252 signals | Max latest-252 signals |
|---|---:|---:|---:|---:|
| `large20_not_aligned_long_1000` | 58.621558 | 63.644375 | 70 | 74 |
| `large20_loose_short_1030` | 107.527931 | 111.096774 | 101 | 104 |
| `large10_loose_long_1130` | 106.734854 | 112.749017 | 126 | 130 |
| `large10_loose_short_1230` | 103.628639 | 108.849725 | 116 | 119 |
| `large20_opposite_two_sided_1400` | 105.016522 | 109.047994 | 125 | 129 |

Decision: all five NQ variants retain the ES source mechanics and original 3 x 3 entry-threshold grid. The weakest declared corner is `large20_not_aligned_long_1000` at 58.621558 signals/year and 70 latest-252-session signals, so no density-only grid widening was needed.
