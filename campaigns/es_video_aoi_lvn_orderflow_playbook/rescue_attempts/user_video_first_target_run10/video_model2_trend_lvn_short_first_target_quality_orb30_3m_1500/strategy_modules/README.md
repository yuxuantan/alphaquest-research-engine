# video_model2_trend_lvn_short_first_target_quality_orb30_3m_1500

Entry module: `video_exact_orderflow_playbook`. Exit module: `signal_price` with a first-target proxy.

This run10 variant keeps the Trader Yush completed 3-minute AOI/LVN orderflow mechanics and changes only the one-contract exit approximation: structural high/low target is usable at 1R or better; otherwise fixed-R fallback is tested at 1.5R, 2R, and 3R. No partial exits or dynamic trailing are simulated.
