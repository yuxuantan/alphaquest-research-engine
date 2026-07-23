# Archive revamp retest summary - 2026-06-21

Verdict: FAIL. All 15 archive-derived revamp variants failed the current staged flow.

| Campaign | Variant | Passed stages | Terminal stage | Key metrics |
|---|---:|---:|---|---|
| es_archive_morning_orderflow_hold_retest | broad_large_alignment_1030_flatten_1515 | 0 | limited_core_grid_test | profitable/window rate=0.0; net=-652.5; pf=0.916932; mar=-0.244685; profitable=0/81; passing_benchmark=0 |
| es_archive_morning_orderflow_hold_retest | large10_flow_1030_flatten_1515 | 0 | limited_core_grid_test | profitable/window rate=0.0; net=-1727.5; pf=0.752152; mar=-0.457926; profitable=0/81; passing_benchmark=0 |
| es_archive_morning_orderflow_hold_retest | large20_flow_1030_flatten_1515 | 0 | limited_core_grid_test | profitable/window rate=0.0; net=-1117.5; pf=0.83081; mar=-0.376168; profitable=0/81; passing_benchmark=0 |
| es_archive_morning_orderflow_hold_retest | signed_flow_1030_flatten_1515 | 0 | limited_core_grid_test | profitable/window rate=0.0; net=-1490.0; pf=0.828588; mar=-0.467063; profitable=0/81; passing_benchmark=0 |
| es_archive_morning_orderflow_hold_retest | signed_flow_1030_flatten_1530 | 0 | limited_core_grid_test | profitable/window rate=0.0; net=-1177.5; pf=0.864538; mar=-0.352515; profitable=0/81; passing_benchmark=0 |
| nq_archive_intraday_momentum_retest | long_only_1030_strength_balanced | 1 | limited_monkey_test | net beat=0.776667; dd beat=0.696667; net=1400.0; monkey_runs=300; core_max_dd=2490.0 |
| nq_archive_intraday_momentum_retest | long_only_1030_strength_efficiency | 2 | walk_forward_analysis | profitable/window rate=0.0; net=0.0; pf=0.0; mar=0.0; early_exit=True; passing_windows=0/1 |
| nq_archive_intraday_momentum_retest | priority_short1030_long1130_base | 1 | limited_monkey_test | net beat=0.816667; dd beat=0.68; net=1010.0; monkey_runs=300; core_max_dd=3855.0 |
| nq_archive_intraday_momentum_retest | priority_short1030_long1130_long50 | 1 | limited_monkey_test | net beat=0.913333; dd beat=0.693333; net=2070.0; monkey_runs=300; core_max_dd=3590.0 |
| nq_archive_intraday_momentum_retest | short_only_1030_weakness | 1 | limited_monkey_test | net beat=0.85; dd beat=0.756667; net=645.0; monkey_runs=300; core_max_dd=1595.0 |
| nq_archive_range_compression_retest | id_nr4_prior_session_breakout | 1 | limited_monkey_test | net beat=0.783333; dd beat=0.61; net=670.0; monkey_runs=300; core_max_dd=1025.0 |
| nq_archive_range_compression_retest | nr7_or30_1040_rank_relaxed_138cap | 0 | limited_core_grid_test | profitable/window rate=0.055556; net=120.0; pf=1.009178; mar=0.019792; profitable=3/54; passing_benchmark=0 |
| nq_archive_range_compression_retest | nr7_or30_1045_rank_relaxed_135cap | 0 | limited_core_grid_test | profitable/window rate=0.0; net=-125.0; pf=0.990616; mar=-0.020323; profitable=0/54; passing_benchmark=0 |
| nq_archive_range_compression_retest | nr7_or30_1130_range_capped | 0 | limited_core_grid_test | profitable/window rate=0.074074; net=1350.0; pf=1.11658; mar=0.372107; profitable=4/54; passing_benchmark=1 |
| nq_archive_range_compression_retest | nr7_or30_morning_range_capped | 0 | limited_core_grid_test | profitable/window rate=0.018519; net=30.0; pf=1.00261; mar=0.00612; profitable=1/54; passing_benchmark=0 |
