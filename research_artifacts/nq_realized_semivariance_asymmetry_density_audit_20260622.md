# NQ Realized Semivariance Asymmetry Density Audit

Date: 2026-06-22

Method: feature-threshold count only on `data/external/nq_realized_semivariance_features_20110103_20260612.csv`. No PnL, stop, target, monkey, WFA, Monte Carlo, prop simulation, or holdout result was inspected.

The NQ feature file is built from completed NQ RTH 1-minute OHLC bars and every tradable feature is shifted one completed RTH session.

Density checks for the predeclared grids:
- high prior downside semivariance long: strict rank tail about 50.1 signals/year.
- high prior downside semivariance short: strict rank tail about 71.6 signals/year.
- high prior downside share long: strict rank tail about 49.9 signals/year.
- high prior upside semivariance short: strict rank tail about 51.0 signals/year.
- two-sided 5-day semivariance balance tails: strict two-tail count about 74.7 signals/year.

Decision: PASS_WITH_SPARSE_STRICT_CORNERS. Sparse strict corners are retained and must pass or fail staged benchmark gates without post-result pruning.
