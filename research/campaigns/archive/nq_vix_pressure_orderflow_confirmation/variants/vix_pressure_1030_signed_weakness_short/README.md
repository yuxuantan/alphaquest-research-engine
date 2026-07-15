# vix_pressure_1030_signed_weakness_short

Campaign: `nq_vix_pressure_orderflow_confirmation`.

Mechanic: At 10:30 ET, short NQ only when lagged VIX-change pressure is present and the completed RTH open-to-signal move plus signed aggregate orderflow are not bullish.

Feature timing: `data/external/nq_cboe_vix_level_features_20110103_20260612.csv` uses only VIX observations strictly before the NQ session date. NQ confirmation uses completed RTH bars through the signal bar close only.
