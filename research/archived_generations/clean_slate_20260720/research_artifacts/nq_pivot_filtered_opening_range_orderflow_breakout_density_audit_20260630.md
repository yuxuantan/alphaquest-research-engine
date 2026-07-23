# NQ Pivot-Filtered Opening-Range Orderflow Breakout Density Audit - 2026-06-30

Verdict: FAIL before staged PnL.

No NQ PnL, stop/target outcome, trade net, benchmark row, WFA, Monte Carlo, simulated incubation, or acceptance OOS result was inspected. This audit counts only exact entry-module signal opportunities on prepared five-minute NQ bars across the declared entry-parameter grid.

Session span: 2011-01-03 through 2026-06-12 (15.441 years).
Limited-core reference window from the canonical random-fraction stage window: 2011-02-22 through 2012-09-07 (1.544 years).
Latest-session density window: last 252 sessions.

## Variant Summary

| variant_id | entry_combos | min_full_signals_per_year | min_limited_core_signals_per_year | min_latest_252_signals | full_failures | limited_core_failures | latest_failures |
| --- | --- | --- | --- | --- | --- | --- | --- |
| or15_large10_pivot_flow_breakout_1030 | 9 | 59.191223 | 58.932181 | 54 | 0 | 0 | 0 |
| or15_signed_pivot_flow_breakout_1030 | 9 | 60.356915 | 63.465426 | 57 | 0 | 0 | 0 |
| or30_large20_pivot_flow_breakout_1100 | 9 | 40.151596 | 36.265957 | 35 | 9 | 9 | 9 |
| or30_signed_pivot_flow_breakout_1100 | 9 | 53.233245 | 48.570479 | 58 | 0 | 3 | 0 |
| or60_signed_pivot_flow_breakout_1200 | 9 | 31.732713 | 29.789894 | 34 | 9 | 9 | 9 |

## Failing Rows

| variant_id | entry_combo | full_signals | signals_per_year_full | limited_core_signals | signals_per_year_limited_core | latest_252_signals | failed_gates |
| --- | --- | --- | --- | --- | --- | --- | --- |
| or30_large20_pivot_flow_breakout_1100 | entry.params.base_params.breakout_buffer_ticks=0,entry.params.base_params.min_orderflow_imbalance=0.0 | 647 | 41.900133 | 56 | 36.265957 | 37 | full,limited_core,latest_252 |
| or30_large20_pivot_flow_breakout_1100 | entry.params.base_params.breakout_buffer_ticks=0,entry.params.base_params.min_orderflow_imbalance=0.02 | 642 | 41.576330 | 56 | 36.265957 | 36 | full,limited_core,latest_252 |
| or30_large20_pivot_flow_breakout_1100 | entry.params.base_params.breakout_buffer_ticks=0,entry.params.base_params.min_orderflow_imbalance=0.04 | 640 | 41.446809 | 56 | 36.265957 | 36 | full,limited_core,latest_252 |
| or30_large20_pivot_flow_breakout_1100 | entry.params.base_params.breakout_buffer_ticks=1,entry.params.base_params.min_orderflow_imbalance=0.0 | 635 | 41.123005 | 57 | 36.913564 | 36 | full,limited_core,latest_252 |
| or30_large20_pivot_flow_breakout_1100 | entry.params.base_params.breakout_buffer_ticks=1,entry.params.base_params.min_orderflow_imbalance=0.02 | 630 | 40.799202 | 57 | 36.913564 | 35 | full,limited_core,latest_252 |
| or30_large20_pivot_flow_breakout_1100 | entry.params.base_params.breakout_buffer_ticks=1,entry.params.base_params.min_orderflow_imbalance=0.04 | 628 | 40.669681 | 57 | 36.913564 | 35 | full,limited_core,latest_252 |
| or30_large20_pivot_flow_breakout_1100 | entry.params.base_params.breakout_buffer_ticks=2,entry.params.base_params.min_orderflow_imbalance=0.0 | 627 | 40.604920 | 56 | 36.265957 | 36 | full,limited_core,latest_252 |
| or30_large20_pivot_flow_breakout_1100 | entry.params.base_params.breakout_buffer_ticks=2,entry.params.base_params.min_orderflow_imbalance=0.02 | 622 | 40.281117 | 56 | 36.265957 | 35 | full,limited_core,latest_252 |
| or30_large20_pivot_flow_breakout_1100 | entry.params.base_params.breakout_buffer_ticks=2,entry.params.base_params.min_orderflow_imbalance=0.04 | 620 | 40.151596 | 56 | 36.265957 | 35 | full,limited_core,latest_252 |
| or30_signed_pivot_flow_breakout_1100 | entry.params.base_params.breakout_buffer_ticks=0,entry.params.base_params.min_orderflow_imbalance=0.0 | 852 | 55.176064 | 75 | 48.570479 | 63 | limited_core |
| or30_signed_pivot_flow_breakout_1100 | entry.params.base_params.breakout_buffer_ticks=1,entry.params.base_params.min_orderflow_imbalance=0.0 | 848 | 54.917021 | 76 | 49.218085 | 63 | limited_core |
| or30_signed_pivot_flow_breakout_1100 | entry.params.base_params.breakout_buffer_ticks=2,entry.params.base_params.min_orderflow_imbalance=0.0 | 846 | 54.787500 | 76 | 49.218085 | 63 | limited_core |
| or60_signed_pivot_flow_breakout_1200 | entry.params.base_params.breakout_buffer_ticks=0,entry.params.base_params.min_orderflow_imbalance=0.0 | 534 | 34.582181 | 52 | 33.675532 | 35 | full,limited_core,latest_252 |
| or60_signed_pivot_flow_breakout_1200 | entry.params.base_params.breakout_buffer_ticks=0,entry.params.base_params.min_orderflow_imbalance=0.02 | 530 | 34.323138 | 51 | 33.027926 | 35 | full,limited_core,latest_252 |
| or60_signed_pivot_flow_breakout_1200 | entry.params.base_params.breakout_buffer_ticks=0,entry.params.base_params.min_orderflow_imbalance=0.04 | 521 | 33.740293 | 49 | 31.732713 | 34 | full,limited_core,latest_252 |
| or60_signed_pivot_flow_breakout_1200 | entry.params.base_params.breakout_buffer_ticks=1,entry.params.base_params.min_orderflow_imbalance=0.0 | 522 | 33.805053 | 48 | 31.085106 | 35 | full,limited_core,latest_252 |
| or60_signed_pivot_flow_breakout_1200 | entry.params.base_params.breakout_buffer_ticks=1,entry.params.base_params.min_orderflow_imbalance=0.02 | 518 | 33.546011 | 48 | 31.085106 | 35 | full,limited_core,latest_252 |
| or60_signed_pivot_flow_breakout_1200 | entry.params.base_params.breakout_buffer_ticks=1,entry.params.base_params.min_orderflow_imbalance=0.04 | 512 | 33.157447 | 49 | 31.732713 | 34 | full,limited_core,latest_252 |
| or60_signed_pivot_flow_breakout_1200 | entry.params.base_params.breakout_buffer_ticks=2,entry.params.base_params.min_orderflow_imbalance=0.0 | 499 | 32.315559 | 46 | 29.789894 | 35 | full,limited_core,latest_252 |
| or60_signed_pivot_flow_breakout_1200 | entry.params.base_params.breakout_buffer_ticks=2,entry.params.base_params.min_orderflow_imbalance=0.02 | 495 | 32.056516 | 46 | 29.789894 | 35 | full,limited_core,latest_252 |
| or60_signed_pivot_flow_breakout_1200 | entry.params.base_params.breakout_buffer_ticks=2,entry.params.base_params.min_orderflow_imbalance=0.04 | 490 | 31.732713 | 47 | 30.437500 | 34 | full,limited_core,latest_252 |

## Density-Passing Rows Kept For Audit

| variant_id | entry_combo | full_signals | signals_per_year_full | limited_core_signals | signals_per_year_limited_core | latest_252_signals |
| --- | --- | --- | --- | --- | --- | --- |
| or15_large10_pivot_flow_breakout_1030 | entry.params.base_params.breakout_buffer_ticks=0,entry.params.base_params.min_orderflow_imbalance=0.0 | 946 | 61.263564 | 94 | 60.875000 | 55 |
| or15_large10_pivot_flow_breakout_1030 | entry.params.base_params.breakout_buffer_ticks=0,entry.params.base_params.min_orderflow_imbalance=0.02 | 937 | 60.680718 | 94 | 60.875000 | 54 |
| or15_large10_pivot_flow_breakout_1030 | entry.params.base_params.breakout_buffer_ticks=0,entry.params.base_params.min_orderflow_imbalance=0.04 | 937 | 60.680718 | 95 | 61.522606 | 54 |
| or15_large10_pivot_flow_breakout_1030 | entry.params.base_params.breakout_buffer_ticks=1,entry.params.base_params.min_orderflow_imbalance=0.0 | 936 | 60.615957 | 92 | 59.579787 | 55 |
| or15_large10_pivot_flow_breakout_1030 | entry.params.base_params.breakout_buffer_ticks=1,entry.params.base_params.min_orderflow_imbalance=0.02 | 928 | 60.097872 | 92 | 59.579787 | 54 |
| or15_large10_pivot_flow_breakout_1030 | entry.params.base_params.breakout_buffer_ticks=1,entry.params.base_params.min_orderflow_imbalance=0.04 | 928 | 60.097872 | 93 | 60.227394 | 54 |
| or15_large10_pivot_flow_breakout_1030 | entry.params.base_params.breakout_buffer_ticks=2,entry.params.base_params.min_orderflow_imbalance=0.0 | 923 | 59.774069 | 91 | 58.932181 | 55 |
| or15_large10_pivot_flow_breakout_1030 | entry.params.base_params.breakout_buffer_ticks=2,entry.params.base_params.min_orderflow_imbalance=0.02 | 914 | 59.191223 | 91 | 58.932181 | 54 |
| or15_large10_pivot_flow_breakout_1030 | entry.params.base_params.breakout_buffer_ticks=2,entry.params.base_params.min_orderflow_imbalance=0.04 | 914 | 59.191223 | 92 | 59.579787 | 54 |
| or15_signed_pivot_flow_breakout_1030 | entry.params.base_params.breakout_buffer_ticks=0,entry.params.base_params.min_orderflow_imbalance=0.0 | 1024 | 66.314894 | 105 | 67.998670 | 63 |
| or15_signed_pivot_flow_breakout_1030 | entry.params.base_params.breakout_buffer_ticks=0,entry.params.base_params.min_orderflow_imbalance=0.02 | 999 | 64.695878 | 100 | 64.760638 | 62 |
| or15_signed_pivot_flow_breakout_1030 | entry.params.base_params.breakout_buffer_ticks=0,entry.params.base_params.min_orderflow_imbalance=0.04 | 955 | 61.846410 | 104 | 67.351064 | 58 |
| or15_signed_pivot_flow_breakout_1030 | entry.params.base_params.breakout_buffer_ticks=1,entry.params.base_params.min_orderflow_imbalance=0.0 | 1011 | 65.473005 | 101 | 65.408245 | 63 |
| or15_signed_pivot_flow_breakout_1030 | entry.params.base_params.breakout_buffer_ticks=1,entry.params.base_params.min_orderflow_imbalance=0.02 | 988 | 63.983511 | 98 | 63.465426 | 62 |
| or15_signed_pivot_flow_breakout_1030 | entry.params.base_params.breakout_buffer_ticks=1,entry.params.base_params.min_orderflow_imbalance=0.04 | 941 | 60.939761 | 100 | 64.760638 | 58 |
| or15_signed_pivot_flow_breakout_1030 | entry.params.base_params.breakout_buffer_ticks=2,entry.params.base_params.min_orderflow_imbalance=0.0 | 1003 | 64.954920 | 101 | 65.408245 | 63 |
| or15_signed_pivot_flow_breakout_1030 | entry.params.base_params.breakout_buffer_ticks=2,entry.params.base_params.min_orderflow_imbalance=0.02 | 981 | 63.530186 | 99 | 64.113032 | 61 |
| or15_signed_pivot_flow_breakout_1030 | entry.params.base_params.breakout_buffer_ticks=2,entry.params.base_params.min_orderflow_imbalance=0.04 | 932 | 60.356915 | 99 | 64.113032 | 57 |
| or30_signed_pivot_flow_breakout_1100 | entry.params.base_params.breakout_buffer_ticks=0,entry.params.base_params.min_orderflow_imbalance=0.02 | 854 | 55.305585 | 78 | 50.513298 | 62 |
| or30_signed_pivot_flow_breakout_1100 | entry.params.base_params.breakout_buffer_ticks=0,entry.params.base_params.min_orderflow_imbalance=0.04 | 838 | 54.269415 | 81 | 52.456117 | 59 |
| or30_signed_pivot_flow_breakout_1100 | entry.params.base_params.breakout_buffer_ticks=1,entry.params.base_params.min_orderflow_imbalance=0.02 | 848 | 54.917021 | 78 | 50.513298 | 61 |
| or30_signed_pivot_flow_breakout_1100 | entry.params.base_params.breakout_buffer_ticks=1,entry.params.base_params.min_orderflow_imbalance=0.04 | 829 | 53.686569 | 80 | 51.808511 | 58 |
| or30_signed_pivot_flow_breakout_1100 | entry.params.base_params.breakout_buffer_ticks=2,entry.params.base_params.min_orderflow_imbalance=0.02 | 846 | 54.787500 | 78 | 50.513298 | 61 |
| or30_signed_pivot_flow_breakout_1100 | entry.params.base_params.breakout_buffer_ticks=2,entry.params.base_params.min_orderflow_imbalance=0.04 | 822 | 53.233245 | 80 | 51.808511 | 58 |
