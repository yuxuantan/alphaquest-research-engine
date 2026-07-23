# ES Profile-AOI Footprint Trap Confluence Density Audit

Date: 2026-06-21

This is a pre-PnL density audit. It used the validated Sierra footprint imbalance cache and counted at most one raw signal per RTH session before any staged PnL run.

Dataset: `data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.parquet`
Rows after feature build/subset: 1,488,630
Sessions: 3,817
Period: 2011-01-03 through 2026-06-09

Rejected before PnL: a one-sided prior-low seller-trap long stayed below the 50 signals/year floor even with broad confluence distance. It was not staged.

Approved final variants:

| Variant | Representative density evidence |
| --- | --- |
| prior_extreme_profile_two_sided_trap_1500 | 80.8-92.2 raw sessions/year across dist 16/32/64 and abs 20/50/100 |
| opening_profile_two_sided_morning_trap_1200 | derived from ORL and ORH morning components; both sides clear the floor in aggregate |
| opening_profile_two_sided_trap_1500 | 100.3-142.8 raw sessions/year across dist 16/32/64 and abs 20/50/100 |
| orl_profile_seller_trap_long_1500 | 56.4-79.3 raw sessions/year across dist 16/32/64 and abs 20/50/100 |
| orh_profile_buyer_trap_short_1500 | 56.8-86.8 raw sessions/year across dist 16/32/64 and abs 20/50/100 |

Data caveat: the full-history cache does not contain validated vendor-equivalent ES >200-lot print fields. This campaign uses footprint absorption at price and profile/AOI confluence; any true >200-lot branch is data-gated.

Decision: approve for staged testing before PnL.
