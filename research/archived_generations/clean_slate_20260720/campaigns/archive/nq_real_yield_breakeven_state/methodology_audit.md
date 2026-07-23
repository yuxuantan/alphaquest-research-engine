# NQ Real-Yield and Breakeven State Methodology Audit

Status: FAIL after staged validation.

This campaign is a new NQ state-variable test based on lagged FRED real-yield and breakeven observations. It is not a ChartFanatics strategy and not a sibling of the failed nominal Treasury-rate tests: the signal decomposes nominal rates into TIPS real yield and inflation-compensation components.

No-lookahead controls:
- `tools/build_nq_real_yield_breakeven_features.py` maps each NQ RTH session to the latest FRED observation strictly before the session date.
- Signals use only the completed 1-minute bar ending at the configured decision time.
- Entry occurs no earlier than the next bar open through the staged engine.
- No same-session FRED value, future NQ bar, final session level, VWAP, profile, or orderflow is used.

Predeclared density gate:
- Full-history signals per year must be at least 50.
- Limited-core window `2011-02-22` through `2012-09-07` must be at least 50 signals/year.
- Latest 252 sessions must contain at least 50 signals.

Density result: PASS. The audit in `research_artifacts/nq_real_yield_breakeven_state_density_audit_20260630.md` recorded 15/15 declared density rows passing.

Staged validation result: FAIL.
- Four variants failed `limited_core_grid_test`.
- `breakeven_1d_up_long_1000` passed `limited_core_grid_test` but failed `limited_monkey_test`.
- The monkey failure was strict: core net-profit beat rate was 0.8845 and max-drawdown beat rate was 0.795125, both below the required 0.90.
- No variant reached WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, or acceptance OOS.

No rescue is authorized or attempted. Do not relaunch this real-yield/breakeven decomposition as a renamed NQ edge without a materially different economic hypothesis and explicit duplicate-edge review.
