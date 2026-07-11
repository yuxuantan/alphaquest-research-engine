VALIDATION_DASHBOARD_PORT ?= 8502
VALIDATION_DASHBOARD_SEARCH_ROOT ?= backtest-campaigns
SAMPLE_VALIDATION_RUN_DIR ?= examples/validation_runs/sample_core

.PHONY: test lint quality qualify cleanup-generated preflight run-catalog validation-dashboard sample-validation-run validation-dashboard-sample

test:
	PYTHONPATH=src python3 -m pytest

lint:
	PYTHONPATH=src python3 -m ruff check src research tests tools

quality: lint test

qualify:
	PYTHONPATH=src python3 tools/qualify_engine.py

cleanup-generated:
	PYTHONPATH=src python3 tools/cleanup_redundant_generated_artifacts.py

preflight:
	PYTHONPATH=src python3 -m research.preflight --skip-tests

run-catalog:
	PYTHONPATH=src python3 tools/build_run_catalog.py

validation-dashboard:
	PYTHONPATH=src PROPSTACK_VALIDATION_SEARCH_ROOT=$(VALIDATION_DASHBOARD_SEARCH_ROOT) streamlit run apps/validation_dashboard.py --server.port $(VALIDATION_DASHBOARD_PORT)

sample-validation-run:
	PYTHONPATH=src python3 -m propstack.validation.sample_run --output-dir $(SAMPLE_VALIDATION_RUN_DIR)

validation-dashboard-sample: sample-validation-run
	PYTHONPATH=src PROPSTACK_VALIDATION_SEARCH_ROOT=examples/validation_runs streamlit run apps/validation_dashboard.py --server.port $(VALIDATION_DASHBOARD_PORT)
