VALIDATION_DASHBOARD_PORT ?= 8502
VALIDATION_DASHBOARD_SEARCH_ROOT ?= research/evidence/runs
SAMPLE_VALIDATION_RUN_DIR ?= examples/validation_runs/sample_core
STUDIO_PORT ?= 8501

.PHONY: help setup studio-setup studio studio-status studio-stop smoke tutorial docs-check test lint quality qualify cleanup-generated research-audit remediation-review preflight run-catalog research-registry research-status research-definitions run-uids run-store storage-audit storage-migration-verify research-workspace validation-dashboard sample-validation-run validation-dashboard-sample

help:
	@printf '%s\n' \
	  'setup                 Install the package with development dependencies' \
	  'studio-setup          Install development and Research Studio dependencies' \
	  'studio                Launch the local Research Studio in the browser' \
	  'studio-status         Show the local Research Studio process status' \
	  'studio-stop           Stop the background Research Studio process' \
	  'smoke                 Run fast CLI, registry, preflight, and engine tests' \
	  'tutorial              Generate and execute the isolated synthetic tutorial' \
	  'docs-check            Validate local links in onboarding documentation' \
	  'test                  Run the complete test suite' \
	  'quality               Run lint and the complete test suite' \
	  'preflight             Audit all authored campaign configs without rerunning tests' \
	  'research-workspace    Rebuild registry, exports, views, run UIDs, and storage audit' \
	  'research-status       Print the registry summary' \
	  'qualify               Write the durable engine qualification report' \
	  'cleanup-generated     Dry-run generated-artifact cleanup' \
	  'research-audit        Write current-truth, lineage, validation, and cleanup audits' \
	  'remediation-review    Prepare the immutable historical human-review boundary' \
	  'storage-migration-verify Verify the manifest, historical paths, and run UIDs'

setup:
	python3 -m pip install -c constraints/dev.txt -e ".[dev]"

studio-setup:
	python3 -m pip install -c constraints/dev.txt -e ".[dev,studio]"

studio:
	PYTHONPATH=src python3 -m alphaquest.cli studio start --port $(STUDIO_PORT)

studio-status:
	PYTHONPATH=src python3 -m alphaquest.cli studio status

studio-stop:
	PYTHONPATH=src python3 -m alphaquest.cli studio stop

smoke:
	PYTHONPATH=src python3 -m pytest -q tests/test_cli.py tests/test_preflight.py tests/test_research_registry.py tests/test_backtest_contracts.py

tutorial:
	PYTHONPATH=src python3 -m alphaquest.cli tutorial

docs-check:
	PYTHONPATH=src python3 tools/check_docs_links.py

test:
	PYTHONPATH=src python3 -m pytest

lint:
	PYTHONPATH=src python3 -m ruff check src research tests tools

quality: lint test

qualify:
	PYTHONPATH=src python3 tools/qualify_engine.py

cleanup-generated:
	PYTHONPATH=src python3 tools/cleanup_redundant_generated_artifacts.py

research-audit:
	PYTHONPATH=src python3 tools/audit_research_repository.py

remediation-review:
	PYTHONPATH=src python3 tools/prepare_historical_remediation_review.py

preflight:
	PYTHONPATH=src python3 -m alphaquest.research.preflight --skip-tests

run-catalog:
	PYTHONPATH=src python3 tools/build_run_catalog.py

research-registry:
	PYTHONPATH=src python3 tools/build_research_registry.py

research-status:
	PYTHONPATH=src python3 -m alphaquest.cli research status

research-definitions:
	PYTHONPATH=src python3 tools/normalize_campaign_definitions.py --apply

run-uids:
	PYTHONPATH=src python3 tools/backfill_run_uids.py --apply

run-store:
	PYTHONPATH=src python3 tools/build_run_store_index.py --apply

storage-audit:
	PYTHONPATH=src python3 tools/write_storage_migration_audit.py

storage-migration-verify:
	PYTHONPATH=src python3 tools/migrate_research_storage.py --verify

research-workspace: run-uids research-registry run-store storage-audit

validation-dashboard:
	PYTHONPATH=src PROPSTACK_VALIDATION_SEARCH_ROOT=$(VALIDATION_DASHBOARD_SEARCH_ROOT) streamlit run apps/validation_dashboard.py --server.port $(VALIDATION_DASHBOARD_PORT)

sample-validation-run:
	PYTHONPATH=src python3 -m alphaquest.validation.sample_run --output-dir $(SAMPLE_VALIDATION_RUN_DIR)

validation-dashboard-sample: sample-validation-run
	PYTHONPATH=src PROPSTACK_VALIDATION_SEARCH_ROOT=examples/validation_runs streamlit run apps/validation_dashboard.py --server.port $(VALIDATION_DASHBOARD_PORT)
