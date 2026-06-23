# NQ CBOE Put/Call Sentiment Density Audit

Date: 2026-06-22

Method: feature-threshold count only on `data/external/nq_cboe_put_call_features_20110103_20260612.csv`. No PnL, stop, target, monkey, WFA, Monte Carlo, prop simulation, or holdout result was inspected.

The NQ feature file was built with `tools/build_es_cboe_put_call_features.py` using the NQ RTH bar cache as the session calendar. CBOE daily ratios are merged strictly before the NQ session date.

Density checks for the predeclared grids:
- low equity put/call rank <= 0.50/0.475/0.45: at least about 58.9 signals/year at the strict edge.
- high equity put/call rank >= 0.60/0.625/0.65: strict edge about 49.7 signals/year.
- falling total put/call one-day change rank <= 0.45/0.40/0.375: strict edge about 50.8 signals/year.
- rising total put/call one-day change rank >= 0.60/0.625/0.63: strict edge about 51.7 signals/year near 0.625.
- high total-minus-equity spread rank >= 0.65/0.675/0.69: strict edge remains near/above the 50/year floor.

Decision: PASS_WITH_SPARSE_STRICT_CORNERS. Sparse strict corners are left in the declared grid and must pass or fail the benchmark gates without post-result pruning.
