# spy_3d_volume_attention_continuation_1530

Campaign: `nq_spy_turnover_orderflow_attention`

Mechanic: NQ two-sided continuation using Prior SPY 3-day return direction with 63-day abnormal volume rank. Completed same-session NQ movement and aggregate signed orderflow must agree before next-bar entry.

Feature timing: `data/external/nq_spy_turnover_attention_features_20110103_20260612.csv` maps only SPY daily observations strictly before the NQ session date.

Entry module: `spy_turnover_orderflow_attention`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.
