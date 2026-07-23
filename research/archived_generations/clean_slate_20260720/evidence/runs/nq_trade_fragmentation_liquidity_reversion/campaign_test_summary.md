# NQ Trade Fragmentation Liquidity Reversion Campaign Summary

Verdict: FAIL.

Rejected before staged NQ PnL: 2/45 declared entry-grid rows failed the 50 signals/year limited-core density gate. The sparse rows were in midday_30m_fragmented_up_fade_short at trade_count_rank_threshold=0.65 with avg_trade_size_rank_threshold 0.50 and 0.55. Dropping those strict short-side rows after this screen would be post-result narrowing of the declared five-variant edge. No NQ PnL was inspected.

Density summary:

| variant | rows | pass rows | min full/year | min limited/year | min latest-252 | verdict |
|---|---:|---:|---:|---:|---:|---|
| `day_60m_fragmented_two_sided_fade` | 9 | 9 | 129.87 | 98.49 | 153 | PASS_DENSITY_ONLY |
| `midday_30m_fragmented_down_fade_long` | 9 | 9 | 70.65 | 52.98 | 90 | PASS_DENSITY_ONLY |
| `midday_30m_fragmented_up_fade_short` | 9 | 7 | 60.01 | 41.43 | 64 | FAIL |
| `morning_15m_fragmented_down_fade_long` | 9 | 9 | 71.24 | 53.66 | 78 | PASS_DENSITY_ONLY |
| `morning_15m_fragmented_up_fade_short` | 9 | 9 | 58.89 | 52.30 | 60 | PASS_DENSITY_ONLY |

Density audit: `research_artifacts/nq_trade_fragmentation_liquidity_reversion_density_audit_20260630.md`.

No staged PnL, monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run.
