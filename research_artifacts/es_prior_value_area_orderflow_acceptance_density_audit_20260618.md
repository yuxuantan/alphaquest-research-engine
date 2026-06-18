# ES Prior Value Area Orderflow Acceptance Density Audit - 2026-06-18

Data source: local Sierra aggregate orderflow parquet only (`data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`). No paid data was downloaded.

Prepared strategy timeframe: 5m; full subset: 2011-01-03 through 2026-06-09.
Limited core window from current stage defaults: 2011-02-22 through 2012-09-06; mode=random_fraction, fraction=0.10, avoid_last_fraction=0.10, seed=31, avoid_range=2020-02-01 through 2021-06-30.

Strict entry density corner used before PnL: `breakout_buffer_ticks=2`, `min_orderflow_imbalance=0.04`, `min_prior_profile_bars=50`, `value_area_fraction=0.70`.

| variant | full signals/year | full signals | limited signals/year | limited signals | long/short full | long/short limited |
|---|---:|---:|---:|---:|---:|---:|
| morning_signed_vah_acceptance_long | 128.75 | 1987 | 121.97 | 188 | 1987/0 | 188/0 |
| morning_signed_val_acceptance_short | 102.70 | 1585 | 109.64 | 169 | 0/1585 | 0/169 |
| late_morning_large10_two_sided_acceptance | 225.36 | 3478 | 227.06 | 350 | 1953/1525 | 181/169 |
| midday_signed_two_sided_acceptance | 219.07 | 3381 | 212.79 | 328 | 1898/1483 | 176/152 |
| afternoon_large20_two_sided_acceptance | 223.22 | 3445 | 218.63 | 337 | 1943/1502 | 186/151 |

Decision: APPROVE_FOR_TESTING. Strict-corner density minimum is 102.70/year full-history and 109.64/year in the limited-core window, both above the 50 trades/year screen.

Lookahead note: prior value area, POC, and VAH/VAL are computed only after the previous RTH session has completed. The current session contributes no bars to its own prior-value profile.
Profile approximation note: Sierra aggregate minute bars do not provide true volume-at-price. The module approximates prior-session volume-at-price by distributing each completed 5-minute bar volume uniformly across its high-low tick range. This is acceptable only as completed-bar aggregate research and is not tick-level volume-profile truth.
