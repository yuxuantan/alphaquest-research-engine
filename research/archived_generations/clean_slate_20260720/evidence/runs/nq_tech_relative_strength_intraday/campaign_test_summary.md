# NQ Tech Relative Strength Intraday - Campaign Summary

Verdict: FAIL

Four NQ tech-relative-strength variants failed the limited core grid. `tech_5d_weakness_short_1130` passed core but failed the limited monkey/randomized schedule gate, with only 18.85% profitable randomized schedules and median randomized net of -2370.0. No variant reached WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Terminal stage | Core profitable | Core rate | Top net | Top PF | Top trades | Top MAR | Monkey profitable |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| tech_1d_strength_long_1000 | limited_core_grid_test | 0/27 | 0.0 | -4812.5 | 0.712429 | 139 | -0.458102 |  |
| tech_1d_weakness_short_1000 | limited_core_grid_test | 0/27 | 0.0 | -5292.5 | 0.735771 | 146 | -0.468684 |  |
| tech_5d_strength_long_1030 | limited_core_grid_test | 3/27 | 0.111111 | 1095.0 | 1.044162 | 182 | 0.172597 |  |
| tech_5d_weakness_short_1130 | limited_monkey_test | 20/27 | 0.740741 | 2400.0 | 1.168126 | 140 | 0.66688 | 0.1885 |
| tech_attention_strength_long_1330 | limited_core_grid_test | 0/81 | 0.0 | -2232.5 | 0.631296 | 64 | -0.451087 |  |

No rescue was authorized or used.
