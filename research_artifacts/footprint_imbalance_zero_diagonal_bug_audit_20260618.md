# Footprint Imbalance Zero-Diagonal Bug Audit

Date: 2026-06-18

Decision: BUG CONFIRMED AND FIXED

## File Investigated

- `data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.parquet`
- Target bar: `2026-06-09 09:30:00`

## Symptom

Before the fix, the target bar showed:

- `high = 7460.00`
- `footprint_highest_sell_imbalance_price = 7460.00`
- `footprint_sell_imbalance_count = 2`
- `footprint_max_sell_imbalance_ratio = 0.0`

This was internally inconsistent: a nonzero sell-imbalance count should not have a zero maximum ratio.

## Root Cause

The footprint generator compared sell pressure as:

- bid volume at price P / ask volume at price P + one tick

and buy pressure as:

- ask volume at price P / bid volume at price P - one tick

The old implementation treated a missing or zero opposite-side diagonal level as an infinite imbalance. That created false edge-of-bar imbalances:

- any sufficiently large bid at the bar high could become a sell imbalance because there is no ask volume one tick above the bar high;
- any sufficiently large ask at the bar low could become a buy imbalance because there is no bid volume one tick below the bar low.

For the target bar, raw ESM26 price-level reconstruction showed:

| price | bid_volume | ask_volume | ask_above | sell_ratio |
| ---: | ---: | ---: | ---: | ---: |
| 7458.75 | 256 | 324 | 67 | 3.820896 |
| 7460.00 | 26 | 113 | 0 | infinite under old rule |

The valid sell imbalance is 7458.75. The 7460.00 mark was a zero-denominator artifact.

## Code Fix

Updated `src/propstack/data/footprint.py` so a diagonal imbalance requires an observed opposite-side comparison level:

- sell imbalance now requires `ask_above > 0`;
- buy imbalance now requires `bid_below > 0`.

Added a regression test in `tests/test_footprint_features.py` to reject zero-opposite diagonal imbalances at bar extremes.

## Regenerated Cache Verification

The parquet cache and validation JSON were rebuilt from local Sierra raw parquet files only. No external or paid data was downloaded.

Regenerated file summary:

- rows: `1,489,410`
- duplicate timestamps: `0`
- absorption long bars: `178,268`
- absorption short bars: `172,491`
- first timestamp: `2010-12-29 09:30:00`
- last timestamp: `2026-06-09 15:59:00`

The corrected target row now shows:

- `high = 7460.00`
- `footprint_highest_sell_imbalance_price = 7458.75`
- `footprint_sell_imbalance_count = 1`
- `footprint_max_sell_imbalance_ratio = 3.820896`
- `footprint_max_sell_imbalance_volume = 256`

Global post-fix consistency checks:

- sell rows: `985,638`
- sell rows with highest sell imbalance exactly at bar high: `0`
- buy rows: `985,890`
- buy rows with lowest buy imbalance exactly at bar low: `0`
- sell rows with nonzero count and zero max ratio: `0`
- buy rows with nonzero count and zero max ratio: `0`

## Impact

Any footprint absorption campaign evidence produced before this fix used the old cache and should be treated as stale if the footprint edge is revisited. The old `es_footprint_absorption_initiation` campaign failed, but its counts, fixed-config trade logs, and staged summaries are not current evidence for the corrected footprint feature contract.

## Corrected-Cache Rerun

After the cache rebuild, all 10 source configs using this parquet were rerun:

- five original `es_footprint_absorption_initiation` variants;
- five one-time parameter-space rescue configs.

All 10 reruns failed `limited_core_grid_test` on the corrected cache. Aggregate corrected-cache evidence was regenerated under `backtest-campaigns/es_footprint_absorption_initiation/`, and `research_ledger.csv` was updated to mark the footprint rows as corrected-cache rerun evidence.

## Verification Commands

- `PYTHONPATH=src:. python3 -m pytest tests/test_footprint_features.py tests/test_footprint_absorption_initiation.py -q`
- `PYTHONPATH=src:. python3 tools/build_sierra_footprint_feature_cache.py --output-parquet data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.parquet --report-json data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.validation.json`
- `PYTHONPATH=src:. python3 -m research.preflight --skip-tests --config <10 footprint configs>`
- `PYTHONPATH=src:. python3 -m propstack.run_campaign_stages --config <each footprint config> --skip-validation --fast-runtime-defaults`
