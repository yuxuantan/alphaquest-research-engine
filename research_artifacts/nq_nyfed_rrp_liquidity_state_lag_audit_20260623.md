# NQ NY Fed RRP Liquidity State Lag Audit - 2026-06-23

The NQ campaign reuses `data/external/nyfed_rrp_liquidity_state_lag1_features_20140811_20260529.csv`, which was built from the local `data/external/liquidity_risk_capacity_features.csv` by shifting all non-date feature columns forward by one listed `trade_date`. No external or paid data was downloaded for the NQ port.

The tradable RRP field is `reverserepo_total_bil_diff5_z504`; valid lagged rows span 2014-08-11 through 2026-05-29. The shift means a signal on trade date T can only use the feature value computed from the prior listed row.
