# production_income_weak_pullback_long_1100

Campaign: `es_chicagofed_cfnai_activity_pullback`

Mechanic: At 11:00 ET, long ES after a completed-bar RTH pullback when the lagged CFNAI production and income component is at or below the predeclared weak-activity threshold. The entry uses the completed bar ending at 11:00:00 and relies on engine next-bar execution.

Why this expresses the edge: Production and income are the most cyclical CFNAI components, so a weak reading can represent below-trend real activity and higher required equity risk compensation. The intraday pullback filter avoids buying solely because of a stale monthly state and requires current-session discounting before entry.

Feature timing: `data/external/es_chicagofed_cfnai_activity_features_20110103_20260609.csv` assigns only the latest CFNAI row whose conservative eligible date is on or before the ES session date.

Entry module: `chicagofed_cfnai_activity_state`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.
