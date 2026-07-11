VALIDATION_DASHBOARD_PORT ?= 8502
VALIDATION_DASHBOARD_SEARCH_ROOT ?= backtest-campaigns
SAMPLE_VALIDATION_RUN_DIR ?= examples/validation_runs/sample_core

.PHONY: validation-dashboard sample-validation-run validation-dashboard-sample

validation-dashboard:
	PYTHONPATH=src PROPSTACK_VALIDATION_SEARCH_ROOT=$(VALIDATION_DASHBOARD_SEARCH_ROOT) streamlit run apps/validation_dashboard.py --server.port $(VALIDATION_DASHBOARD_PORT)

sample-validation-run:
	PYTHONPATH=src python3 -m propstack.validation.sample_run --output-dir $(SAMPLE_VALIDATION_RUN_DIR)

validation-dashboard-sample: sample-validation-run
	PYTHONPATH=src PROPSTACK_VALIDATION_SEARCH_ROOT=examples/validation_runs streamlit run apps/validation_dashboard.py --server.port $(VALIDATION_DASHBOARD_PORT)
