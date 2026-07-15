# high_macro_news_rebound_long_1130

Mechanic: At 11:30 ET, long NQ when lagged monthly EMV macro-news rank is in the upper tail, testing a compensating risk-premium interpretation.

Signal state is computed from `data/external/nq_emv_macro_news_features_20110103_20260612.csv`, where each monthly EMV observation becomes eligible only after observation month-end plus 21 calendar days. The entry signal is evaluated on the completed 1-minute bar immediately before the configured entry time, so fills occur no earlier than the next bar open.
