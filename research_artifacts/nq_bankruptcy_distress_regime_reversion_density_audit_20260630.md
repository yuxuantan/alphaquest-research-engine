# NQ Bankruptcy Distress Regime Reversion Density Audit

Review date: 2026-06-30

Scope: pre-PnL density and signal/entry-bar availability audit for all 15 declared entry-threshold rows.

Feature CSV: `data/external/uscourts_bankruptcy_f2_quarterly_features.csv`
Raw bars: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`

Gate: full-history density >= 50 signals/year, latest-1260-session density >= 50 signals/year, latest-252-session signals >= 20, and zero missing signal/entry bars for each configured entry time.

| variant_id | rows | pass_rows | min_full_signals_per_year | min_latest_1260_signals_per_year | min_latest_252_signals | pass_variant_density_gate |
| --- | --- | --- | --- | --- | --- | --- |
| business_ch11_growth_prior_down_long_1130 | 3 | 1 | 12.928303 | 20.741617 | 0 | False |
| business_ch11_share_prior_down_long_1330 | 3 | 1 | 16.491221 | 22.51947 | 35 | False |
| chapter11_share_prior_down_long_1330 | 3 | 1 | 16.389423 | 22.321931 | 35 | False |
| total_ch11_growth_prior_down_long_1130 | 3 | 1 | 15.167851 | 21.334235 | 0 | False |
| total_ch11_z_prior_up_short_1330 | 3 | 1 | 19.646948 | 30.816117 | 45 | False |

Conclusion: FAIL.
10 declared entry-threshold rows failed density or bar-availability gates. Staged PnL should not proceed.
