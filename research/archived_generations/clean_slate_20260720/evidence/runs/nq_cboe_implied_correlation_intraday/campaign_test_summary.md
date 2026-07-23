# NQ Cboe Implied Correlation Intraday - Campaign Summary

Verdict: FAIL

High short-term correlation passed core and monkey but failed WFA. Low COR3M passed core but failed monkey. The other three variants failed the limited core grid. No variant reached WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Terminal stage | Core profitable | Top net | Top PF | Top trades | Top MAR | Monkey | WFA |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| high_cor3m_short_1000 | limited_core_grid_test | 1/27 | 900.0 | 1.0424428200896014 | 146 | 0.2994030659974137 | skipped | skipped |
| low_cor3m_long_1030 | limited_monkey_test | 19/27 | 1767.5 | 1.2075748678802114 | 92 | 1.074696194731845 | failed | skipped |
| rising_cor3m_short_1130 | limited_core_grid_test | 8/27 | 1935.0 | 1.1109836535704043 | 139 | 0.4233561908060204 | skipped | skipped |
| falling_cor3m_long_1200 | limited_core_grid_test | 13/27 | 1800.0 | 1.193029490616622 | 129 | 1.236046265003683 | skipped | skipped |
| high_short_term_correlation_short_1330 | walk_forward_analysis | 24/27 | 5240.0 | 1.3884358784284656 | 141 | 2.0652794828366114 | passed | failed |

No rescue was authorized or used.
