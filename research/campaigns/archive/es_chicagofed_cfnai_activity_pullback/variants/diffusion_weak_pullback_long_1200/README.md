# diffusion_weak_pullback_long_1200

Campaign: `es_chicagofed_cfnai_activity_pullback`

Mechanic: At 12:00 ET, long ES after a completed-bar RTH pullback when the lagged CFNAI diffusion index is at or below the predeclared weak-breadth threshold. The entry uses the completed bar ending at 12:00:00 and relies on engine next-bar execution.

Why this expresses the edge: Weak diffusion means the activity slowdown is broad rather than isolated in one component. A broad weak-growth state can raise required equity compensation, and the noon pullback condition tests that thesis only after current-session selling pressure is observable.

Feature timing: `data/external/es_chicagofed_cfnai_activity_features_20110103_20260609.csv` assigns only the latest CFNAI row whose conservative eligible date is on or before the ES session date.

Entry module: `chicagofed_cfnai_activity_state`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.
