# Methodology Audit - NQ Opening-Drive MES Crowding Reversal

Verdict: FAIL as of 2026-06-30T13:03:16+08:00.

Source and duplicate review:
- Source ES campaign: `es_opening_drive_mes_crowding_reversal`, an ES opening-drive failed-extension/MES-crowding edge that did not pass full staged validation.
- The NQ port is distinct from existing NQ opening-drive inventory/orderflow work because MES participation supplies the crowding evidence at the failed extension.
- The NQ port is distinct from other MES-crowding campaigns because the price trigger is a frozen opening-drive extreme and completed failed continuation back inside that extreme.

No-lookahead and execution checks:
- Opening-drive high, low, open, close, and direction are frozen only after the configured opening-drive window completes.
- Signal bars are completed 1-minute bars after the drive window; entries are no earlier than next-bar open under the engine timing test.
- MES participation ranks are local cache fields built from current completed bars and prior same-clock observations; no future session high/low, VWAP, final volume profile, or post-entry outcome is used.
- Configs include NQ tick size, point value, commission, one-tick slippage, same-day flatten, and Apex-style flatten controls.

Pre-PnL density result:
- Detail CSV: `research_artifacts/nq_opening_drive_mes_crowding_reversal_density_audit_20260630.csv`
- Audit artifact: `research_artifacts/nq_opening_drive_mes_crowding_reversal_density_audit_20260630.md`
- Result: PASS. Every predeclared entry-grid corner for every variant exceeded 50 entry-condition signals/year in both full-history and limited-core reference windows before PnL was inspected.

Staged result:
- `od15_notional_failed_extension_reversal_1130`: limited core passed; limited monkey failed. Core beat random-entry net profit 0.887625, below the 0.90 gate; drawdown beat rate 0.474625.
- `od15_trade_failed_extension_reversal_1130`: limited core passed; limited monkey failed. Core beat random-entry net profit 0.922125, but drawdown beat rate was only 0.712750.
- `od30_notional_failed_extension_reversal_1300`: limited core failed with 0.0 profitable iteration rate; best row net profit -2705.0 and PF 0.8098.
- `od30_trade_failed_extension_reversal_1300`: limited core failed with 0.0 profitable iteration rate; best row net profit -2495.0 and PF 0.8239.
- `od60_notional_failed_extension_reversal_1530`: limited core failed with 0.0 profitable iteration rate; best row net profit -4445.0 and PF 0.6728.

Terminal decision:
- FAIL. No variant reached WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting. No rescue was authorized or run.
