# NQ Intraday Periodicity Orderflow Confirmation Density Audit - 2026-06-23

Pre-PnL signal-density screen only. Source bars: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`.
Feature file: `data/external/nq_intraday_periodicity_features_20110103_20260612.csv`, built with prior-slot rolling returns shifted by one prior occurrence.

Result: PASS with pre-PnL grid pruning. Fixed `min_mean_return_bps=0.75`; selected entry grid is `lookback_days=[10,20,40]` x `min_orderflow_imbalance=[0.0,0.01]`.

The raw `0.02` orderflow-threshold corner was rejected before PnL because `morning_1000_signed_confirmed_slot` fell to 49.8098 signals/year at the weakest lookback. The selected grid's weakest corner is 72.4152 signals/year.

| variant | selected-grid min signals/year |
|---|---:|
| morning_1000_signed_confirmed_slot | 72.4152 |
| morning_1030_large10_confirmed_slot | 100.5263 |
| late_morning_1130_signed_confirmed_slot | 75.0709 |
| afternoon_1330_large20_confirmed_slot | 82.3254 |
| late_afternoon_1430_large20_confirmed_slot | 92.6241 |

Full raw count table, including the rejected threshold corner: `research_artifacts/nq_intraday_periodicity_orderflow_confirmation_density_audit_20260623.csv`.

No PnL, stop, target, monkey, WFA, Monte Carlo, incubation, acceptance, or holdout result was inspected.
