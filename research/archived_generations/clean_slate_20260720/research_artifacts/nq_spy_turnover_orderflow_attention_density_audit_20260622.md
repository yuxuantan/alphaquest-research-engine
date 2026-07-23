# NQ SPY Turnover Orderflow Attention Density Audit

Date: 2026-06-22

Method: entry-condition counts only on NQ 5-minute aggregated RTH bars and `data/external/nq_spy_turnover_attention_features_20110103_20260612.csv`. Counts use the module logic of one first qualifying signal per day, prior SPY feature row, NQ session-open-to-signal move, and aggregate NQ signed-volume confirmation. No PnL, stop, target, monkey, WFA, Monte Carlo, prop simulation, or holdout result was inspected.

Fixed NQ scale choice before PnL: `min_es_move_ticks` is set to 8 NQ ticks because the inherited module parameter means session-open-to-signal index move; 8 NQ ticks is roughly the same notional/percentage scale as the ES campaign's 2 ES ticks.

Shared parameter grid: attention rank threshold `[0.55, 0.60, 0.65]`, orderflow imbalance `[0.0, 0.003, 0.006]`, stop `[0.003, 0.004, 0.006]`, target `[1.0, 1.5, 2.0]`.

Strict-corner signal counts with attention 0.65 and orderflow imbalance 0.006 were about 44-46/year across variants; broad corners were about 67-69/year. Decision: PASS_WITH_SPARSE_STRICT_CORNERS. Sparse strict corners are allowed to fail the trade-count benchmark instead of being removed after PnL.
