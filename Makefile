VALIDATION_DASHBOARD_PORT ?= 8502
VALIDATION_DASHBOARD_SEARCH_ROOT ?= research/evidence/runs
SAMPLE_VALIDATION_RUN_DIR ?= examples/validation_runs/sample_core
STUDIO_PORT ?= 8501
NPM ?= npm
PYTHON ?= python3

.PHONY: help setup studio-setup studio-ui-setup studio studio-status studio-stop studio-ui-check studio-ui-build smoke tutorial docs-check test-python test-execution test methodology-regression causal-execution-regression lint quality validate qualify cleanup-generated research-audit remediation-review preflight run-catalog research-registry research-status research-definitions run-uids run-store storage-audit storage-migration-verify research-workspace validation-dashboard sample-validation-run validation-dashboard-sample

help:
	@printf '%s\n' \
	  'setup                 Install the pinned Python reference environment' \
	  'studio-setup          Compatibility alias for setup' \
	  'studio-ui-setup       Install the locked React developer dependencies' \
	  'studio                Launch the local Research Studio in the browser' \
	  'studio-status         Show the local Research Studio process status' \
	  'studio-stop           Stop the background Research Studio process' \
	  'studio-ui-check       Type-check and test the React UI (developer; requires Node.js)' \
	  'studio-ui-build       Build committed React UI assets (developer; requires Node.js)' \
	  'smoke                 Run fast CLI, registry, preflight, and engine tests' \
	  'tutorial              Generate and execute the isolated synthetic tutorial' \
	  'docs-check            Validate local links in onboarding documentation' \
	  'test-python           Run the governed Python suite under tests/' \
	  'test-execution        Run execution_system/tests independently' \
	  'test                  Run the complete Python test surface' \
	  'methodology-regression Run the focused methodology regression surface' \
	  'causal-execution-regression Run the focused causal/execution regression surface' \
	  'quality               Run lint and the complete Python test surface' \
	  'validate              Run every hermetic engineering CI category' \
	  'preflight             Audit all authored campaign configs without rerunning tests' \
	  'research-workspace    Rebuild registry, exports, views, run UIDs, and storage audit' \
	  'research-status       Print the registry summary' \
	  'qualify               Write the durable engine qualification report' \
	  'cleanup-generated     Dry-run generated-artifact cleanup' \
	  'research-audit        Write current-truth, lineage, validation, and cleanup audits' \
	  'remediation-review    Prepare the immutable historical human-review boundary' \
	  'storage-migration-verify Verify the manifest, historical paths, and run UIDs'

setup:
	$(PYTHON) -m pip install -c constraints/dev.txt -e ".[dev,studio,dashboard]"

studio-setup: setup

studio-ui-setup:
	$(NPM) --prefix studio-ui ci

studio:
	PYTHONPATH=src $(PYTHON) -m alphaquest.cli studio start --port $(STUDIO_PORT)

studio-status:
	PYTHONPATH=src $(PYTHON) -m alphaquest.cli studio status

studio-stop:
	PYTHONPATH=src $(PYTHON) -m alphaquest.cli studio stop

studio-ui-check:
	$(NPM) --prefix studio-ui run check
	$(NPM) --prefix studio-ui run test

studio-ui-build:
	$(NPM) --prefix studio-ui run build

smoke:
	PYTHONPATH=src $(PYTHON) -m pytest -q tests/test_cli.py tests/test_preflight.py tests/test_research_registry.py tests/test_backtest_contracts.py

tutorial:
	PYTHONPATH=src $(PYTHON) -m alphaquest.cli tutorial

docs-check:
	PYTHONPATH=src $(PYTHON) tools/check_docs_links.py

test-python:
	PYTHONPATH=src $(PYTHON) -m pytest tests

test-execution:
	PYTHONPATH=src $(PYTHON) -m pytest execution_system/tests

test:
	PYTHONPATH=src $(PYTHON) -m pytest

methodology-regression:
	PYTHONPATH=src $(PYTHON) -m pytest -q \
	  tests/test_research_policy.py \
	  tests/test_research_governance.py \
	  tests/test_campaign_stages.py \
	  tests/test_wfa.py \
	  tests/test_monte_carlo.py \
	  tests/test_research_execution.py \
	  tests/test_run_store.py \
	  tests/test_experiment_registry.py \
	  tests/test_strategy_certification.py \
	  tests/test_execution_certification.py \
	  tests/test_validation_promotion_gate.py \
	  tests/test_data_source_hash.py

causal-execution-regression:
	PYTHONPATH=src $(PYTHON) -m pytest -q \
	  tests/test_backtest_contracts.py \
	  tests/test_backtest_engine.py \
	  tests/test_order_simulation.py \
	  tests/test_sessions.py \
	  tests/test_event_replay.py \
	  tests/test_event_replay_partial_exit.py \
	  tests/test_position_sizing.py \
	  tests/test_backtest_live_parity.py \
	  tests/test_forward_reconciliation.py \
	  tests/test_studio_execution_contract.py

lint:
	PYTHONPATH=src $(PYTHON) -m ruff check src research tests tools apps execution_system

quality: lint test

validate: lint docs-check smoke methodology-regression causal-execution-regression test studio-ui-check

qualify:
	PYTHONPATH=src $(PYTHON) tools/qualify_engine.py

cleanup-generated:
	PYTHONPATH=src $(PYTHON) tools/cleanup_redundant_generated_artifacts.py

research-audit:
	PYTHONPATH=src $(PYTHON) tools/audit_research_repository.py

remediation-review:
	PYTHONPATH=src $(PYTHON) tools/prepare_historical_remediation_review.py

preflight:
	PYTHONPATH=src $(PYTHON) -m alphaquest.research.preflight --skip-tests

run-catalog:
	PYTHONPATH=src $(PYTHON) tools/build_run_catalog.py

research-registry:
	PYTHONPATH=src $(PYTHON) tools/build_research_registry.py

research-status:
	PYTHONPATH=src $(PYTHON) -m alphaquest.cli research status

research-definitions:
	PYTHONPATH=src $(PYTHON) tools/normalize_campaign_definitions.py --apply

run-uids:
	PYTHONPATH=src $(PYTHON) tools/backfill_run_uids.py --apply

run-store:
	PYTHONPATH=src $(PYTHON) tools/build_run_store_index.py --apply

storage-audit:
	PYTHONPATH=src $(PYTHON) tools/write_storage_migration_audit.py

storage-migration-verify:
	PYTHONPATH=src $(PYTHON) tools/migrate_research_storage.py --verify

research-workspace: run-uids research-registry run-store storage-audit

validation-dashboard:
	PYTHONPATH=src PROPSTACK_VALIDATION_SEARCH_ROOT=$(VALIDATION_DASHBOARD_SEARCH_ROOT) $(PYTHON) -m streamlit run apps/validation_dashboard.py --server.port $(VALIDATION_DASHBOARD_PORT)

sample-validation-run:
	PYTHONPATH=src $(PYTHON) -m alphaquest.validation.sample_run --output-dir $(SAMPLE_VALIDATION_RUN_DIR)

validation-dashboard-sample: sample-validation-run
	PYTHONPATH=src PROPSTACK_VALIDATION_SEARCH_ROOT=examples/validation_runs $(PYTHON) -m streamlit run apps/validation_dashboard.py --server.port $(VALIDATION_DASHBOARD_PORT)
