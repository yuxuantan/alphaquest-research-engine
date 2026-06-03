# Test Commands

Run commands from the repo root.

## Choose A Variant

```bash
export VARIANT_CONFIG=configs/campaigns/five_min_orb_vol_filter/variants/ES/1m_full_history/baseline.yaml
```

Other current variant configs:

```bash
export VARIANT_CONFIG=configs/campaigns/intraday_capitulation_mr/variants/MES/1m_full_history/baseline.yaml
export VARIANT_CONFIG=configs/campaigns/pdh_pdl_sweep/variants/ES/1m_full_history/baseline.yaml
export VARIANT_CONFIG=configs/campaigns/pdh_pdl_sweep/variants/ES/1m_full_history/core_grid_rescue.yaml
```

## Campaign Tests

```bash
PYTHONPATH=src python3 -m propstack.run_core --config "$VARIANT_CONFIG"
PYTHONPATH=src python3 -m propstack.run_core_grid --config "$VARIANT_CONFIG"
PYTHONPATH=src python3 -m propstack.run_monkey --config "$VARIANT_CONFIG"
PYTHONPATH=src python3 -m propstack.run_wfa --config "$VARIANT_CONFIG"
PYTHONPATH=src python3 -m propstack.run_monte_carlo --config "$VARIANT_CONFIG"
```

Monte Carlo reads an existing report trade log. Use `monte_carlo.trade_source:
core` after `propstack.run_core`, or `monte_carlo.trade_source: wfa_oos` after
`propstack.run_wfa`.

Arguments for all campaign tests:

```text
--config PATH        Required variant YAML path.
--skip-validation   Optional. Skip writing cleaned/features validation CSVs.
```

Repeated full-history WFA example:

```bash
PYTHONPATH=src python3 -m propstack.run_wfa --config "$VARIANT_CONFIG" --skip-validation
```

## Data Source Comparison

```bash
PYTHONPATH=src python3 -m propstack.compare_data_sources \
  --csv data/raw/ES/es_1m_20221201-20260529.csv \
  --dbn-dir data/raw/ES/GLBX-20260601-U6S3S4F4GM \
  --out data/reports/data_compare/ES/rithmic_vs_databento_1m \
  --symbol ES \
  --timezone America/New_York \
  --continuous-contract explicit_roll_calendar \
  --roll-calendar configs/data/ES/motivewave_rithmic_roll_calendar.csv \
  --price-tolerance 0.0 \
  --volume-tolerance 0.0 \
  --detail-limit 100000
```

Optional data comparison arguments:

```text
--cache-dir PATH
--start-timestamp TIMESTAMP
--end-timestamp TIMESTAMP
--start-date YYYY-MM-DD
--end-date YYYY-MM-DD
--continuous-contract dominant_session_volume|session_volume|explicit_roll_calendar|none
--skip-alternate-contract-check
```

## Python Tests

```bash
pytest
pytest tests/test_wfa.py
pytest tests/test_core_grid.py tests/test_monkey.py tests/test_monte_carlo.py
pytest tests/test_wfa.py tests/test_progress.py
```
