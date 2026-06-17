# ma3_activity_weak_pullback_long_1130

Campaign: `es_chicagofed_cfnai_activity_pullback`

Mechanic: At 11:30 ET, long ES after a completed-bar RTH pullback when the lagged three-month moving average of CFNAI is at or below the predeclared weak-activity threshold. The entry uses the completed bar ending at 11:30:00 and relies on engine next-bar execution.

Why this expresses the edge: The three-month average reduces single-release noise and better represents persistent below-trend activity. The later signal time gives the cash session more time to reveal a real pullback while still leaving a same-day exit window before the configured flatten cutoff.

Feature timing: `data/external/es_chicagofed_cfnai_activity_features_20110103_20260609.csv` assigns only the latest CFNAI row whose conservative eligible date is on or before the ES session date.

Entry module: `chicagofed_cfnai_activity_state`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.
