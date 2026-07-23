# ES Prior Value Area Orderflow Acceptance Rescue Density Audit - 2026-06-18

Limited core window: 2011-02-22 through 2012-09-06.
Strict rescue corner: `breakout_buffer_ticks=3`, `min_orderflow_imbalance=0.02`.

| variant | full signals/year | full signals | limited signals/year | limited signals |
|---|---:|---:|---:|---:|
| morning_signed_vah_acceptance_long | 129.33 | 1996 | 120.67 | 186 |
| morning_signed_val_acceptance_short | 104.06 | 1606 | 107.04 | 165 |
| late_morning_large10_two_sided_acceptance | 224.13 | 3459 | 226.42 | 349 |
| midday_signed_two_sided_acceptance | 217.26 | 3353 | 208.25 | 321 |
| afternoon_large20_two_sided_acceptance | 221.60 | 3420 | 217.33 | 335 |

Decision: APPROVE_RESCUE_FOR_TESTING. Minimum limited-core strict-corner density is 107.04/year.
