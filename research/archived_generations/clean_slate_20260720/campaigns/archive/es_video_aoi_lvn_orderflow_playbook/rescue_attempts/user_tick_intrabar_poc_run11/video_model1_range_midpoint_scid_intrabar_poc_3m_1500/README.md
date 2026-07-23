# video_model1_range_midpoint_scid_intrabar_poc_3m_1500

POC variant for `video_exact_orderflow_playbook_scid_intrabar`.

This keeps the run5 Model 1 value-edge idea but changes entry timing:

- Prior completed 3-minute cached developing VAP/AOI context supplies VAL/VAH.
- Sierra SCID records are replayed inside the current 3-minute bar.
- Entry triggers on the first SCID record that satisfies the probe/reclaim, accumulated confluence, and SCID-record absorption-proxy checks.

Source-quality caveat: Sierra SCID records are not exchange MBO sequencing. The intrabar absorption check is a record-level bid/ask-volume proxy, not the original completed-bar footprint imbalance study.
