# Methodology Audit: nq_mes_flow_price_extension_reversion

Verdict: FAIL

This campaign tests a distinct NQ expression of cross-index micro-flow reversion. A signal is allowed only when completed MES/NQ flow pressure and completed NQ price extension point in the same direction by the signal close; the trade then fades that extension.

No-lookahead controls:
- The raw file is `data/cache/orderflow/nq_mes_flow_divergence_1m_20190506_20260612_full_rth_ny.csv`.
- Entry modules consume the bar whose close equals the configured signal timestamp.
- Engine execution is next-bar-open or later after the completed signal bar.
- No final session range, final VWAP, future NQ return, future MES flow, or post-entry data is used.

Pre-PnL density:
- Artifact: `research_artifacts/nq_mes_flow_price_extension_reversion_density_audit_20260623.md`
- CSV: `research_artifacts/nq_mes_flow_price_extension_reversion_density_audit_20260623.csv`
- Minimum declared entry-corner density: 57.848844 signals/year.
- Maximum declared entry-corner density: 139.625434 signals/year.

Parameter discipline:
- Entry parameters: `flow_threshold`, `min_return_ticks`.
- Stop parameter: `stop_pct`.
- Take-profit parameter: `target_r_multiple`.
- Total combinations per variant: 81.

Known caveats:
- MES is a cross-index proxy, not native MNQ orderflow.
- The prior NQ MES micro-flow branch failed monkey robustness, so this campaign must pass the complete staged workflow before it can be considered a candidate strategy.
- A pass would still be only a candidate requiring manual due diligence and incubation.

Result:
- Decision: FAIL.
- Four variants failed `limited_core_grid_test`.
- `morning15_mes_buy_nq_up_extension_short_1000` passed limited core with 59/81 profitable combinations and 34 benchmark-pass combinations, then failed `limited_monkey_test` with net-beat rate 0.838125 and drawdown-beat rate 0.551375.
- No variant reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance, or candidate reporting.
