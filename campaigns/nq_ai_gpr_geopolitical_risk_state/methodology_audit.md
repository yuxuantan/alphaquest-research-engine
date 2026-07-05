# NQ AI-GPR Geopolitical Risk State Methodology Audit

This campaign was selected after checking the active NQ tree and ledger for duplicate external-risk campaigns. It is distinct from failed EPU, EMV macro-news, OFR stress, VIX/VVIX, oil-price-return, credit-stress, and style-factor families because the driver is lagged geopolitical-risk news intensity and its threats/acts decomposition.

Signals use the public AI-GPR daily file with a 30-calendar-day availability lag. For a session dated D, the feature builder joins only the latest AI-GPR observation on or before D minus 30 calendar days. Intraday entries use a completed one-minute NQ RTH bar and may fill no earlier than the next bar open.

Important caveat: the AI-GPR page provides historical daily data but does not prove a historical real-time release cadence for each daily observation. This is handled by a conservative lag and must remain a manual-review item if anything passes the full staged pipeline.

Each of the five variants has one tunable entry parameter, one stop parameter, and one take-profit parameter. No rescue is authorized after staged results.

Pre-PnL density passed 15/15 declared entry rows and 5/5 variants. No PnL was inspected before this campaign source set was frozen.

Final staged decision: FAIL. All five variants failed `limited_core_grid_test`; the best profitable-combination rate was `0.2962962962962963` versus the required `0.70`. No branch reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.
