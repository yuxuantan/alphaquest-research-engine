# diffusion_weak_pullback_long_1200

Campaign: `nq_chicagofed_cfnai_activity_pullback`

Mechanic: At 12:00 ET, long NQ after a completed-bar RTH pullback when the lagged CFNAI CFNAI diffusion index is at or below the predeclared weak-activity threshold. The entry uses the completed bar ending at 12:00:00 and relies on engine next-bar execution.

Why this expresses the edge: the CFNAI state is a lagged real-activity condition, while the intraday pullback requires current-session NQ discounting before entry. The ES source family failed, so this variant is only a predeclared NQ transfer test and must pass the staged pipeline on its own.

Feature timing: `data/external/nq_chicagofed_cfnai_activity_features_20110103_20260612.csv` assigns only the latest CFNAI row whose conservative eligible date is on or before the NQ session date.

Entry module: `chicagofed_cfnai_activity_state`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.
