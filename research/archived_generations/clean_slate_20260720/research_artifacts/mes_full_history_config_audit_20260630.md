# MES Full-History Config Audit - 2026-06-30

## Scope

User request: check whether any ES strategy source configs still used MES-derived data for less than the available project history, and switch them to the full-history local data already present in the repo.

This audit updates stale source configs under `campaigns/` and verifies generated `backtest-campaigns/` source/effective config snapshots for MES-derived caches. It does not change any strategy mechanics or promote any failed strategy result.

## Available ES/MES Caches

- `data/cache/orderflow/es_mes_flow_divergence_1m_20190506_20260609_full_rth_ny.csv`
  - Rows: 685,230 data rows.
  - Timestamp span: `2019-05-06 09:30:00` through `2026-06-09 15:59:00`.
  - Columns: 139.
- `data/cache/orderflow/es_mes_participation_crowding_1m_20190506_20260609_full_rth_ny.csv`
  - Timestamp span: `2019-05-06 09:30:00` through `2026-06-09 15:59:00`.
  - Columns: 158.
- `data/cache/orderflow/es_mes_footprint_liquidity_sweep_1m_20190506_20260609_full_rth_ny.parquet`
  - Timestamp span: `2019-05-06 09:30:00` through `2026-06-09 15:59:00`.
  - Columns: 50.
- `data/cache/orderflow/es_mes_crowding_vap_aoi_1m_20190506_20250529_rth_ny.parquet`
  - Timestamp span: `2019-05-06 09:30:00` through `2025-05-29 15:59:00`.
  - Columns: 191.
- `data/cache/orderflow/mes_sierra_trade_orderflow_1m_20190506_20260616_full_rth_ny.csv`
  - Timestamp span: `2019-05-06 09:30:00` through `2026-06-16 15:59:00`.
  - Columns: 16.
- `data/cache/orderflow/nq_mes_flow_divergence_1m_20190506_20260612_full_rth_ny.csv`
  - Timestamp span: `2019-05-06 09:30:00` through `2026-06-12 15:59:00`.
  - Columns: 139.
- `data/cache/orderflow/nq_mes_participation_crowding_1m_20190506_20260612_full_rth_ny.csv`
  - Timestamp span: `2019-05-06 09:30:00` through `2026-06-12 15:59:00`.
  - Columns: 40.

The older one-year divergence CSVs each have 96,330 data rows:

- `data/cache/orderflow/es_mes_flow_divergence_1m_20250610_20260608.csv`
- `data/cache/orderflow/es_mes_price_flow_divergence_1m_20250610_20260608.csv`

The full-history divergence cache is schema-compatible with the old one-year files: all old flow columns are present, and the old price-flow columns match the full cache.

## Finding

The structured source-config scan found 10 configs still pinned to the one-year ES/MES divergence data window:

- 5 canonical configs under `campaigns/es_mes_micro_flow_divergence_reversion/variants/`
- 5 first parameter-space rescue configs under `campaigns/es_mes_micro_flow_divergence_reversion/rescue_attempts/parameter_space_rescue_1/`

Other ES/MES source configs scanned already used the available full-history span for their cache family. AOI/VAP configs matched the currently available AOI cache span ending `2025-05-29`.

## Changes Made

For the 10 stale configs:

- Replaced one-year dataset ids with `es_mes_flow_divergence_1m_20190506_20260609_full_rth_ny`.
- Replaced raw CSV paths with `data/cache/orderflow/es_mes_flow_divergence_1m_20190506_20260609_full_rth_ny.csv`.
- Replaced core data subset `2025-06-10..2026-06-08` with `2019-05-06..2026-06-09`.

Updated `campaigns/es_mes_micro_flow_divergence_reversion/campaign.yaml` so the campaign-level data requirement now points at the full-history cache and the superseded one-year caches are listed only as historical data-scope context.

## Validation

Command pattern:

```bash
PYTHONPATH=src python3 -m research.preflight --config <updated-config> --skip-tests
```

Result:

- All 10 updated configs returned `Preflight PASS`.
- Preflight emitted the existing mechanics-review warning for these legacy configs: `mechanics review is not marked required`.
- No staged backtests were rerun in this audit.

Additional structured scan:

- Scope: `campaigns/**/config.yaml`, `backtest-campaigns/**/source_config.yaml`, and `backtest-campaigns/**/effective_config.yaml`.
- MES cache families checked:
  - `es_mes_flow_divergence_1m_20190506_20260609_full_rth_ny`
  - `es_mes_participation_crowding_1m_20190506_20260609_full_rth_ny`
  - `es_mes_footprint_liquidity_sweep_1m_20190506_20260609_full_rth_ny`
  - `es_mes_crowding_vap_aoi_1m_20190506_20250529_rth_ny`
  - `nq_mes_flow_divergence_1m_20190506_20260612_full_rth_ny`
  - `nq_mes_participation_crowding_1m_20190506_20260612_full_rth_ny`
- Result: 581 MES-derived source/effective configs matched the available full-history cache span for their cache family.
- Issues found after the update: 0.
- Generated `backtest-campaigns/es_mes_micro_flow_divergence_reversion/**/{source,effective}_config.yaml` snapshots already reference the full-history divergence cache and `2019-05-06..2026-06-09` data subset; no rerun is required solely to correct a stale generated config snapshot.

The string-only hit on `es_prior_lvn_orderflow_rejection` was excluded from MES remediation because it uses `es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny`, not a MES-derived cache. Its `2025-06-10` field belongs to a simulated incubation OOS split, not the main cache span.

## Verdict

PASS

The MES data-window/config audit is complete: no remaining source or generated source/effective config snapshot was found using a shorter-than-available MES-derived cache span. This is not a strategy-validation pass; existing campaign verdicts, including failed staged strategy results, remain unchanged.
