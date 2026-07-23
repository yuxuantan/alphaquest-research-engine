# Databento ES Trades Download Stopped - 2026-06-16

Status: stopped by user request.

Command scope:
- Dataset: `GLBX.MDP3`
- Schema: `trades`
- Symbol: `ES.FUT`
- Dates: `2020-01-01` through `2026-06-09`
- Session: RTH `09:30:00` to `16:00:00` America/New_York
- Output directory: `data/raw/ES/databento-es-trades-2020-2026`

Fresh dry-run estimate before download:
- ES estimate: `$554.49`
- Manifest: `research_artifacts/databento_es_trades_20200101_20260609_cost_refresh_20260616.json`

Reason stopped:
- The local Sierra Chart ES trade-orderflow cache already provides the ES bar-level trade/orderflow fields needed for the ES/MES divergence branch:
  `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Therefore fetching Databento ES `trades` was unnecessary for this validation path.

Interrupted local state at stop check:
- Completed ES DBN daily files observed: `1250`
- Partial `.part` files observed: `5`
- No completed Databento download manifest was present in the output directory at the stop check.

Use restriction:
- Do not use `data/raw/ES/databento-es-trades-2020-2026` as a complete or validated ES input unless a later run explicitly resumes/completes it and writes a complete manifest.
- Prefer the Sierra ES cache for ES trade-orderflow features in this branch.
