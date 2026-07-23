# NQ Cboe Implied Correlation Intraday Density Audit

Decision: PASS

This is a pre-PnL density audit. It counts only strictly lagged Cboe implied-correlation rank states for each declared threshold. It does not inspect stops, targets, trade PnL, WFA, Monte Carlo, or holdout outcomes.

- Features: `data/external/nq_cboe_implied_correlation_features_20110103_20260612.csv`
- Availability: latest Cboe COR1M/COR3M daily close strictly before NQ session_date.
- Signal times: 10:00, 10:30, 11:30, 12:00, and 13:30 ET.
- Test window for density: 2011-01-03 through 2026-06-12.
- Span years: 15.44.

| Variant | Entry combos | Min candidates | Max candidates | Min/year | Max/year |
|---|---:|---:|---:|---:|---:|
| falling_cor3m_long_1200 | 3 | 1291 | 1665 | 83.61 | 107.83 |
| high_cor3m_short_1000 | 3 | 1072 | 1378 | 69.42 | 89.24 |
| high_short_term_correlation_short_1330 | 3 | 1322 | 1698 | 85.61 | 109.96 |
| low_cor3m_long_1030 | 3 | 1745 | 2055 | 113.01 | 133.08 |
| rising_cor3m_short_1130 | 3 | 1329 | 1708 | 86.07 | 110.61 |

All variants have enough pre-PnL signal density to justify staged testing.
