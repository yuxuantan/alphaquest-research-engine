# vix_pressure_1130_vwap_signed_pressure_short

Campaign: `nq_vix_pressure_orderflow_confirmation`.

Mechanic: At 11:30 ET, short NQ only when lagged VIX-change pressure is present, price is below same-session VWAP, and cumulative signed aggregate orderflow confirms downside pressure.

Feature timing: `data/external/nq_cboe_vix_level_features_20110103_20260612.csv` uses only VIX observations strictly before the NQ session date. NQ confirmation uses completed RTH bars through the signal bar close only.
