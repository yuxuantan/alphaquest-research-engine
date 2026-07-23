# ES intraday capitulation orderflow reversion campaign summary

Decision: FAIL

All five original variants failed limited_core_grid_test with 0.0 profitable-combo rate. Each failed variant received exactly one parameter-space/fixed-parameter rescue preserving the completed downside capitulation, below-VWAP, session-local RSI/volume, and aggregate sell-imbalance reversal mechanic. All five rescues also failed limited_core_grid_test with 0.0 profitable-combo rate and negative top-combo net profit; no run reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Best run: `late_day_10m_capitulation_long_1530/rescue1` top net `-2477.5`, PF `0.6868878357030016`, trades/year `73.57176633697684`.

No candidate strategy report was created.
