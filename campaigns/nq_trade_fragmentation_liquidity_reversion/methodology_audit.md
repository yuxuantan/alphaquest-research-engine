# NQ Trade Fragmentation Liquidity Reversion Methodology Audit

Verdict: FAIL.

Rejected before staged NQ PnL: 2/45 declared entry-grid rows failed the 50 signals/year limited-core density gate. The sparse rows were in midday_30m_fragmented_up_fade_short at trade_count_rank_threshold=0.65 with avg_trade_size_rank_threshold 0.50 and 0.55. Dropping those strict short-side rows after this screen would be post-result narrowing of the declared five-variant edge. No NQ PnL was inspected.

The density audit counted deterministic entry opportunities on completed NQ one-minute bars after building rolling trade-count, average-trade-size, and prior-only same-clock rank features. No stop/target outcomes, trade net, benchmark rows, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting were inspected.

The density-passing variants are only density-passing rows, not candidate strategies. Selecting only those variants or removing the two sparse rows after this screen would violate the predeclared five-variant campaign protocol.
