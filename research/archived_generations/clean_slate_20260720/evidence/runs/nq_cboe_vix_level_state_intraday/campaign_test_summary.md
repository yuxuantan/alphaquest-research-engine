# NQ Cboe VIX Level State Intraday - Campaign Test Summary

Verdict: FAIL

No variant passed the full staged workflow. The campaign is rejected without a NQ rescue attempt.

| variant | terminal_stage | core profitable | core top net | core PF | core trades | monkey status | failure |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| high_vix_rebound_long_1000 | limited_core_grid_test | 0/27 | -72.5 | 0.9849585062240664 | 89 | skipped | failed limited core grid gate |
| low_vix_complacency_short_1030 | limited_core_grid_test | 0/18 | -2165.0 | 0.6370494551550713 | 122 | skipped | failed limited core grid gate |
| persistent_high_vix_long_1330 | limited_core_grid_test | 3/27 | 112.5 | 1.0082266910420474 | 125 | skipped | failed limited core grid gate |
| vix_crush_rebound_long_1200 | limited_core_grid_test | 10/27 | 1255.0 | 1.1035478547854785 | 166 | skipped | failed limited core grid gate |
| vix_spike_riskoff_short_1130 | limited_monkey_test | 27/27 | 7842.5 | 1.420509383378016 | 186 | failed | failed limited monkey/randomized schedule gate |
