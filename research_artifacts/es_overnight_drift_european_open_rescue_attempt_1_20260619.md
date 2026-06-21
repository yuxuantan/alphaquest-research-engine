# es_overnight_drift_european_open rescue attempt 1

Date: 2026-06-19

Scope: five original variants plus one mechanics-preserving parameter-space rescue per failed variant.

Controls:
- No paid data downloaded; used existing local ES Databento OHLCV ETH/RTH cache.
- Entry, stop, target modules, data window, timeframe, signal clocks, costs, slippage, same-bar handling, and flatten gates were unchanged in rescue.
- `target_r_multiple` floor is 1.0 in original corrected configs and rescue configs.
- Preflight passed for all five rescue configs before staged testing.

Outcome:
- Original runs: 5; all failed limited core with 0% profitable combinations.
- Rescue runs: 5; all failed limited core with 0% profitable combinations.
- Best original: `eu_open_down_no_recovery_long_0200` top net `-966.25`, PF `0.6558325912733749`, trades/year `38.06078610603291`.
- Best rescue: `london_open_prior_down_long_0300` top net `-652.5`, PF `0.9037610619469026`, trades/year `58.54904019480725`.
- Fixed-config core trade logs and equity curves were written for all ten runs.

Decision: FAIL. No candidate strategy report was created.
