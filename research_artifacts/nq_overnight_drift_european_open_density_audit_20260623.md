# NQ Overnight Drift European Open Density Audit - 2026-06-23

Pre-PnL signal-density screen only. Source data:
`data/cache/databento/nq_databento_ohlcv_1m_20100606_20260531_eth_rth_explicit_roll.parquet`,
prepared through `propstack.data.pipeline.prepare_data` to 5-minute bars with
`feature_set: full`, ETH/RTH session labels, and prior-RTH features.

Counts cover `2011-01-03` through `2026-05-29`, use fixed ETH signal clocks,
and inspect only signal availability. No stop, target, PnL, benchmark,
monkey, WFA, Monte Carlo, simulated incubation, acceptance, or holdout result
was used.

## Result

PASS with pre-PnL grid pruning. Four variants passed all declared entry
corners. The `eu_open_down_no_recovery_long_0200` variant rejected
`max_pre_signal_return_ticks: 0` before PnL because the stricter prior-down
corners produced fewer than 50 signals/year. Its declared grid therefore uses
`max_pre_signal_return_ticks: [16, 32]`, whose weakest corner is 50.5181
signals/year.

| variant | selected entry corner min signals/year | density decision |
|---|---:|---|
| eu_open_unconditional_long_0200 | 244.6688 | pass |
| eu_open_prior_down_long_0200 | 89.8028 | pass |
| eu_open_down_no_recovery_long_0200 | 50.5181 | pass after rejecting sparse zero-recovery corner |
| eu_open_prior_down_long_0230 | 89.8677 | pass |
| london_open_prior_down_long_0300 | 89.8677 | pass |

Full raw count table: `research_artifacts/nq_overnight_drift_european_open_density_audit_20260623.csv`.

ETH-session and prop-rule eligibility remain manual-review caveats if any
staged result passes.
