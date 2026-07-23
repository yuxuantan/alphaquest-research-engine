# ES Strategy Search Data Gate - 2026-06-29

## Verdict

NEEDS MANUAL REVIEW

This is not a strategy pass. The current local ES search has no full-stage
passing candidate strategy. The latest official local campaign,
`es_opening_vap_large200_acceptance`, failed at `limited_core_grid_test`.

## Local Search State

- `es_opening_vap_large200_acceptance`: FAIL. All five official variants failed
  `limited_core_grid_test` with 0 profitable combinations out of 270 official
  limited-core combinations. No WFA, Monte Carlo, incubation, frozen, or
  acceptance OOS evidence exists for promotion.
- `es_mes_micro_flow_divergence_reversion`: FAIL. The refreshed local ES/MES
  Sierra branch had a complete local merged ES/MES minute cache, but no
  refreshed original or approved rescue reached WFA.
- No existing rejected ES branch was relabeled or mined for a near-miss.

## Retained Ranked Path

The retained next path is the separate ES TBBO quote-liquidity pilot documented
in `research_artifacts/es_quote_liquidity_sweep_pilot_protocol_20260614.md`.

Required feature data is still absent:

- Raw TBBO files: `data/raw/ES/databento-es-tbbo-20250609-20260609/*.tbbo.dbn*`
  are absent.
- Liquidity cache: `data/cache/orderflow/es_tbbo_liquidity_1m_20250609_20260609.csv`
  is absent.

The repo already has the required infrastructure:

- `src/propstack/strategy_modules/entry/quote_liquidity_sweep_reversion.py`
- `src/propstack/build_tbbo_liquidity_cache.py`
- `src/propstack/data/tbbo_liquidity.py`

## Refreshed No-Download Dry Run

Command run:

```bash
PYTHONPATH=src python3 -m propstack.download_databento_rth_trades \
  --start-date 2025-06-09 \
  --end-date 2026-06-09 \
  --out-dir data/raw/ES/databento-es-tbbo-20250609-20260609 \
  --symbols ES.FUT \
  --schema tbbo \
  --stype-in parent \
  --stype-out instrument_id \
  --timezone America/New_York \
  --filter-dataset-condition \
  --estimate-cost sample \
  --sample-days 20 \
  --dry-run \
  --manifest research_artifacts/databento_es_tbbo_20250609_20260609_dry_run_manifest_20260629.json
```

Result:

- Built 262 candidate RTH sessions.
- Dataset-condition filter kept 262 sessions.
- Download plan contains 262 missing or new sessions.
- Sampled 20 sessions.
- Estimated cost: `$5.9504756033411`.
- Manifest: `research_artifacts/databento_es_tbbo_20250609_20260609_dry_run_manifest_20260629.json`.
- Manifest `results` is empty because this was a dry run.
- No paid data was downloaded.

## Required Explicit Approval

Do not run the TBBO pilot download without explicit approval for paid data.
If approved, use a bounded command with a hard cost cap:

```bash
PYTHONPATH=src python3 -m propstack.download_databento_rth_trades \
  --start-date 2025-06-09 \
  --end-date 2026-06-09 \
  --out-dir data/raw/ES/databento-es-tbbo-20250609-20260609 \
  --symbols ES.FUT \
  --schema tbbo \
  --stype-in parent \
  --stype-out instrument_id \
  --timezone America/New_York \
  --filter-dataset-condition \
  --estimate-cost exact \
  --max-cost 10 \
  --paid-data-approved \
  --manifest data/raw/ES/databento-es-tbbo-20250609-20260609/download_manifest.json
```

After the raw TBBO files exist, build the liquidity cache:

```bash
PYTHONPATH=src python3 -m propstack.build_tbbo_liquidity_cache \
  --raw-dir data/raw/ES/databento-es-tbbo-20250609-20260609 \
  --out-csv data/cache/orderflow/es_tbbo_liquidity_1m_20250609_20260609.csv \
  --monthly-cache-dir data/cache/orderflow/es_tbbo_liquidity_monthly \
  --force
```

Only after the cache validates should a five-variant
`es_quote_liquidity_sweep_reversion` campaign be treated as executable staged
research.
