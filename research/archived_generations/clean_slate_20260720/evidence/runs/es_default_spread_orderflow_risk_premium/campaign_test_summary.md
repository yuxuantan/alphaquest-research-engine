# es_default_spread_orderflow_risk_premium

Decision: FAIL.

All five original variants failed limited core. Each failed variant received one parameter-space-only rescue, and all five rescues also failed limited core. No run reached monkey, WFA, Monte Carlo, or frozen validation.

Best original: `high_spread_signed_long_1230` with profitable-combo rate `0.2222222222222222` and `1` benchmark-passing combos.

Best rescue: `high_spread_signed_long_1230` with profitable-combo rate `0.49382716049382713` and `8` benchmark-passing combos. TP was unchanged because all target_r_multiple values were already >= 1.0R.
