# headline_activity_weak_pullback_long_1100

Campaign: `es_chicagofed_cfnai_activity_pullback`

Mechanic: At 11:00 ET, long ES after a completed-bar RTH pullback when the lagged headline CFNAI value is at or below the predeclared weak-activity threshold. The entry uses the completed bar ending at 11:00:00 and relies on engine next-bar execution.

Why this expresses the edge: The headline index aggregates the broad common factor across national activity indicators, which is less sector-specific than any one component. Pairing a weak broad activity state with a same-session pullback tests whether higher business-cycle risk premia are paid intraday after price pressure.

Feature timing: `data/external/es_chicagofed_cfnai_activity_features_20110103_20260609.csv` assigns only the latest CFNAI row whose conservative eligible date is on or before the ES session date.

Entry module: `chicagofed_cfnai_activity_state`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.
