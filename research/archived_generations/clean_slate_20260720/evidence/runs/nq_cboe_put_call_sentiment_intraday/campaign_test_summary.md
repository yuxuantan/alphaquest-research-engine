# NQ CBOE Put/Call Sentiment Intraday - Campaign Summary

Verdict: FAIL

All five variants passed core. Two passed monkey and failed WFA; three failed monkey. No variant reached downstream Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Terminal stage | Core profitable | Top net | Top PF | Monkey | WFA net | WFA PF | WFA MAR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| falling_total_pc_long_1130 | walk_forward_analysis | 27/27 | 6420.0 | 1.4571021715913137 | passed | -2090.0 | 0.8707482993197279 | -0.47633200537886 |
| high_equity_pc_short_1030 | walk_forward_analysis | 27/27 | 5440.0 | 1.2362136343899262 | passed | -5335.0 | 0.8344453064391001 | -0.5295516927947286 |
| high_total_vs_equity_pc_short_1330 | limited_monkey_test | 27/27 | 4380.0 | 1.3969188944268238 | failed | None | None | None |
| low_equity_pc_long_1000 | limited_monkey_test | 20/27 | 1940.0 | 1.1300703989272545 | failed | None | None | None |
| rising_total_pc_short_1200 | limited_monkey_test | 21/27 | 3305.0 | 1.223840162546563 | failed | None | None | None |

No rescue was authorized or used.
