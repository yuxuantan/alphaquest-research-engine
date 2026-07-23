# video_model2_trend_lvn_structural_two_sided_exact_3m_1500

Mechanics: Trade both long and short trend continuations after price accepts beyond developing value and pulls back into a developing LVN with at least two AOI criteria.

Video mapping:
- AOI requires at least two criteria: market level, developing VAP level, ES large-200 record, or delta activity.
- Model 1 uses value-area-edge false breaks in balance.
- Model 2 uses trend pullbacks into same-session developing LVNs.
- Entry is next 3-minute open after the completed signal bar.
- Stop is beyond the signal-bar wick plus offset.
- Target uses the structural target that the single-target simulator can represent.

Data gates:
- 30-second ORB is not in the available historical cache and is not approximated.
- Large-200 is a Sierra aggregate record proxy, not full DOM/MBO sequencing.
- Partial trims, dynamic trailing stops, and add-on entries are not represented by the current engine.
