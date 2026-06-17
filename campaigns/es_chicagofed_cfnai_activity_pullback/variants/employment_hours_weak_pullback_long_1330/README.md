# employment_hours_weak_pullback_long_1330

Campaign: `es_chicagofed_cfnai_activity_pullback`

Mechanic: At 13:30 ET, long ES after a completed-bar RTH pullback when the lagged CFNAI employment, unemployment, and hours component is at or below the predeclared weak-labor threshold. The entry uses the completed bar ending at 13:30:00 and relies on engine next-bar execution.

Why this expresses the edge: Labor-market softness is a central business-cycle input for equity risk premia and policy expectations. The later entry requires a sustained intraday discount under that weak labor state, avoiding a mechanically bullish interpretation of stale macro data alone.

Feature timing: `data/external/es_chicagofed_cfnai_activity_features_20110103_20260609.csv` assigns only the latest CFNAI row whose conservative eligible date is on or before the ES session date.

Entry module: `chicagofed_cfnai_activity_state`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.
