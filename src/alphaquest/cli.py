from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from typing import Any, Iterable

import yaml
import pandas as pd

from alphaquest.research.campaign_stages import run_campaign_stage_tests
from alphaquest.research.definitions import write_definition_manifests
from alphaquest.research.registry import build_registry, export_registry_csvs, generate_views, registry_summary
from alphaquest.research.run_store import backfill_run_uids, build_run_store_index
from alphaquest.research.storage import display_path, load_storage_layout
from alphaquest.utils.config import CAMPAIGN_REPORT_ROOT


DEFAULT_DATABASE = Path("catalogs/research_registry.sqlite")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not getattr(args, "handler", None):
        parser.print_help()
        return 0
    try:
        return int(args.handler(args) or 0)
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="alphaquest", description="Institutional futures research operations CLI.")
    parser.add_argument("--version", action="version", version="alphaquest 0.1.0")
    commands = parser.add_subparsers(dest="command")

    strategy = commands.add_parser("strategy", help="Audit and certify custom strategy implementations.")
    strategy_commands = strategy.add_subparsers(dest="strategy_command")
    strategy_list = strategy_commands.add_parser("list", help="List versioned strategy certifications.")
    strategy_list.add_argument("--project-root", default=".")
    strategy_list.add_argument("--json", action="store_true")
    strategy_list.set_defaults(handler=_strategy_list)
    strategy_audit = strategy_commands.add_parser(
        "audit", help="Verify source hashes, factories, and required certification coverage."
    )
    strategy_audit.add_argument("strategy_id", nargs="?")
    strategy_audit.add_argument("--project-root", default=".")
    strategy_audit.add_argument("--json", action="store_true")
    strategy_audit.set_defaults(handler=_strategy_audit)
    strategy_certify = strategy_commands.add_parser(
        "certify", help="Run declared tests and bind a strategy manifest to the tested source bytes."
    )
    strategy_certify.add_argument("strategy_id")
    strategy_certify.add_argument("--project-root", default=".")
    strategy_certify.add_argument("--json", action="store_true")
    strategy_certify.set_defaults(handler=_strategy_certify)

    account = commands.add_parser("account", help="List and run governed account-specific suitability assessments.")
    account_commands = account.add_subparsers(dest="account_command")
    account_list = account_commands.add_parser("list", help="List reviewed challenge, funded, and live profiles.")
    account_list.add_argument("--project-root", default=".")
    account_list.add_argument("--all", action="store_true", help="Include synthetic and hidden compatibility profiles.")
    account_list.add_argument("--json", action="store_true")
    account_list.set_defaults(handler=_account_list)
    account_assess = account_commands.add_parser(
        "assess", help="Replay frozen trade evidence against one versioned account profile."
    )
    account_assess.add_argument("profile_id")
    account_assess.add_argument("--profile-version")
    account_assess.add_argument("--project-root", default=".")
    account_assess.add_argument("--trades", required=True, help="Acceptance/WFA trade log CSV or Parquet.")
    account_assess.add_argument("--config", required=True, help="Frozen source config used to generate the trades.")
    account_assess.add_argument(
        "--output-root",
        help="Artifact root; defaults to the repository-owned research_artifact_root.",
    )
    account_assess.add_argument("--campaign-id", required=True)
    account_assess.add_argument("--variant-id", required=True)
    account_assess.add_argument("--attempt-id", required=True)
    account_assess.add_argument("--data-sha256", required=True)
    account_assess.add_argument("--strategy-implementation-sha256")
    account_assess.add_argument("--evaluation-price", type=float)
    account_assess.add_argument("--activation-fee", type=float)
    account_assess.add_argument("--other-upfront-costs", type=float, default=0.0)
    account_assess.add_argument("--cost-source")
    account_assess.add_argument("--cost-observed-at")
    account_assess.add_argument("--attest", action="append", default=[])
    account_assess.add_argument("--evaluation-start")
    account_assess.add_argument("--evaluation-end")
    account_assess.add_argument("--runs", type=int)
    account_assess.add_argument("--seed", type=int, default=11)
    account_assess.add_argument("--result-bundle-v2", help="Also create ResultBundleV3 beside this scientific bundle.")
    account_assess.add_argument("--json", action="store_true")
    account_assess.set_defaults(handler=_account_assess)

    workspace = commands.add_parser("workspace", help="Build generated indexes and views.")
    workspace_commands = workspace.add_subparsers(dest="workspace_command")
    workspace_build = workspace_commands.add_parser("build", help="Rebuild the registry, views, and run-store index.")
    workspace_build.add_argument("--project-root", default=".")
    workspace_build.set_defaults(handler=_workspace_build)

    research = commands.add_parser("research", help="Query research state.")
    research_commands = research.add_subparsers(dest="research_command")
    status = research_commands.add_parser("status", help="Show registry summary.")
    _database_argument(status)
    status.add_argument("--json", action="store_true")
    status.set_defaults(handler=_research_status)
    search = research_commands.add_parser("search", help="Search campaigns and run outcomes.")
    _database_argument(search)
    search.add_argument("--query", help="Substring in campaign ID, title, or edge family.")
    search.add_argument("--symbol", choices=("ES", "NQ"))
    search.add_argument("--state", choices=("active", "review_queue", "candidate", "closed"))
    search.add_argument("--verdict", choices=("PASS", "FAIL", "NEEDS_MANUAL_REVIEW"))
    search.add_argument("--failed-stage")
    search.add_argument("--edge-family")
    search.add_argument("--since", help="Minimum run update timestamp or date.")
    search.add_argument("--limit", type=int, default=30)
    search.add_argument("--json", action="store_true")
    search.set_defaults(handler=_research_search)

    edge_backlog = commands.add_parser(
        "edge-backlog",
        help="Capture and govern the canonical pre-hypothesis economic-edge inventory.",
    )
    edge_commands = edge_backlog.add_subparsers(dest="edge_backlog_command")
    capture_observation = edge_commands.add_parser(
        "capture-observation", help="Append the first CODEX-authored observation revision."
    )
    capture_observation.add_argument("--project-root", default=".")
    capture_observation.add_argument("--input", required=True, help="JSON observation payload.")
    capture_observation.add_argument("--actor-id", required=True, help="Provenance only; not authentication.")
    capture_observation.add_argument("--task-id")
    capture_observation.set_defaults(handler=_edge_capture_observation)
    revise_observation = edge_commands.add_parser(
        "revise-observation", help="Append a CODEX-authored observation revision."
    )
    revise_observation.add_argument("observation_id")
    revise_observation.add_argument("--project-root", default=".")
    revise_observation.add_argument("--input", required=True, help="JSON observation payload.")
    revise_observation.add_argument("--actor-id", required=True, help="Provenance only; not authentication.")
    revise_observation.add_argument("--task-id")
    revise_observation.set_defaults(handler=_edge_revise_observation)
    create_edge = edge_commands.add_parser("create", help="Append the first CODEX-authored edge revision.")
    create_edge.add_argument("--project-root", default=".")
    create_edge.add_argument("--input", required=True, help="JSON edge-entry payload.")
    create_edge.add_argument("--actor-id", required=True, help="Provenance only; not authentication.")
    create_edge.add_argument("--task-id")
    create_edge.set_defaults(handler=_edge_create)
    revise_edge = edge_commands.add_parser("revise", help="Append a CODEX-authored unsealed edge revision.")
    revise_edge.add_argument("entry_id")
    revise_edge.add_argument("--project-root", default=".")
    revise_edge.add_argument("--input", required=True, help="JSON edge-entry payload.")
    revise_edge.add_argument("--actor-id", required=True, help="Provenance only; not authentication.")
    revise_edge.add_argument("--task-id")
    revise_edge.set_defaults(handler=_edge_revise)
    edge_list = edge_commands.add_parser("list", help="List current derived entry states.")
    edge_list.add_argument("--project-root", default=".")
    edge_list.add_argument(
        "--state",
        choices=("UNREVIEWED", "REVIEWED_CONTINUE", "REJECTED", "DUPLICATE", "SUSPENDED", "RESUMED"),
    )
    edge_list.add_argument("--json", action="store_true")
    edge_list.set_defaults(handler=_edge_list)
    edge_show = edge_commands.add_parser("show", help="Show one entry with immutable decisions and links.")
    edge_show.add_argument("entry_id")
    edge_show.add_argument("--project-root", default=".")
    edge_show.add_argument("--json", action="store_true")
    edge_show.set_defaults(handler=_edge_show)
    edge_search = edge_commands.add_parser("search", help="Search normalized economic-edge content.")
    edge_search.add_argument("--project-root", default=".")
    edge_search.add_argument("--query")
    edge_search.add_argument(
        "--state",
        choices=("UNREVIEWED", "REVIEWED_CONTINUE", "REJECTED", "DUPLICATE", "SUSPENDED", "RESUMED"),
    )
    edge_search.add_argument("--json", action="store_true")
    edge_search.set_defaults(handler=_edge_search)
    edge_duplicates = edge_commands.add_parser(
        "duplicate-candidates", help="Build the deterministic candidate snapshot for human review."
    )
    edge_duplicates.add_argument("entry_id")
    edge_duplicates.add_argument("--project-root", default=".")
    edge_duplicates.set_defaults(handler=_edge_duplicate_candidates)
    edge_review = edge_commands.add_parser(
        "review", help="Record an immutable HUMAN_OWNER_RESEARCHER backlog disposition."
    )
    edge_review.add_argument("entry_id")
    edge_review.add_argument("--project-root", default=".")
    edge_review.add_argument(
        "--disposition",
        required=True,
        choices=("REVIEWED_CONTINUE", "REJECTED", "DUPLICATE", "SUSPENDED"),
    )
    edge_review.add_argument(
        "--duplicate-resolution",
        required=True,
        choices=("SAME_EDGE", "RELATED_EDGE_FAMILY", "DISTINCT_EDGE", "UNRESOLVED"),
    )
    edge_review.add_argument("--candidate-snapshot-sha256", required=True)
    edge_review.add_argument("--canonical-entry-id")
    edge_review.add_argument("--related-edge-family-id", action="append", default=[])
    edge_review.add_argument(
        "--reason-code",
        action="append",
        required=True,
        choices=(
            "AMBIGUOUS_DUPLICATE",
            "CAUSAL_WEAKNESS",
            "DATA_UNAVAILABLE",
            "DUPLICATE_EDGE",
            "INSUFFICIENT_EVIDENCE",
            "NEW_INFORMATION",
            "OWNER_PRIORITY",
            "PRIOR_FAILURE",
            "SCOPE_MISMATCH",
            "SOURCE_QUALITY",
            "TEMPORARY_BLOCKER",
            "OTHER",
        ),
    )
    edge_review.add_argument("--rationale", required=True)
    edge_review.add_argument("--revisit-condition", action="append", default=[])
    edge_review.add_argument("--reviewer-id", required=True, help="Provenance only; not authentication.")
    edge_review.add_argument("--decision-id")
    edge_review.set_defaults(handler=_edge_review)
    edge_resume = edge_commands.add_parser(
        "resume", help="Record an immutable human resume after a current suspension."
    )
    edge_resume.add_argument("entry_id")
    edge_resume.add_argument("--project-root", default=".")
    edge_resume.add_argument(
        "--reason-code",
        action="append",
        required=True,
        choices=("NEW_INFORMATION", "TEMPORARY_BLOCKER", "OTHER"),
    )
    edge_resume.add_argument("--rationale", required=True)
    edge_resume.add_argument("--reviewer-id", required=True, help="Provenance only; not authentication.")
    edge_resume.add_argument("--decision-id")
    edge_resume.set_defaults(handler=_edge_resume)
    edge_validate = edge_commands.add_parser("validate", help="Validate all canonical backlog history.")
    edge_validate.add_argument("--project-root", default=".")
    edge_validate.set_defaults(handler=_edge_validate)
    edge_bootstrap = edge_commands.add_parser(
        "bootstrap-index", help="Rebuild the deterministic derived historical index."
    )
    edge_bootstrap.add_argument("--project-root", default=".")
    edge_bootstrap.set_defaults(handler=_edge_bootstrap)

    literature = commands.add_parser(
        "literature", help="Create, inspect, validate, and emit the offline canonical P3 literature slice."
    )
    literature_commands = literature.add_subparsers(dest="literature_command")
    literature_pilot = literature_commands.add_parser(
        "openalex-run", help="Run the supervised, one-shot OpenAlex P3 search pilot."
    )
    literature_pilot.add_argument("--project-root", default=".")
    literature_pilot.add_argument("--protocol-revision-sha", required=True)
    literature_pilot.set_defaults(handler=_literature_openalex_run)
    literature_put = literature_commands.add_parser("put-artifact", help="Store one offline content-addressed artifact.")
    literature_put.add_argument("--project-root", default=".")
    literature_put.add_argument("--input", required=True)
    literature_put.add_argument("--kind", required=True, choices=("artifacts", "extracted", "provider-traces", "codex-io"))
    literature_put.set_defaults(handler=_literature_put_artifact)
    literature_append = literature_commands.add_parser("append", help="Append one strict canonical P3 record from JSON.")
    literature_append.add_argument(
        "family",
        choices=("protocol", "search-start", "search-finish", "work", "source-version", "source-relationship", "capture", "claim", "evidence-relation", "dossier", "freeze", "codex-attempt"),
    )
    literature_append.add_argument("--project-root", default=".")
    literature_append.add_argument("--input", required=True)
    literature_append.add_argument("--actor-id", required=True)
    literature_append.add_argument("--actor-class", default="ALPHAQUEST_DETERMINISTIC_ENGINE", choices=("CODEX", "HUMAN_OWNER_RESEARCHER", "ALPHAQUEST_DETERMINISTIC_ENGINE"))
    literature_append.add_argument("--task-id")
    literature_append.add_argument("--idempotency-key", required=True)
    literature_append.set_defaults(handler=_literature_append)
    literature_list = literature_commands.add_parser("list", help="List canonical P3 records in append order.")
    literature_list.add_argument("--project-root", default=".")
    literature_list.add_argument("--family")
    literature_list.set_defaults(handler=_literature_list)
    literature_show = literature_commands.add_parser("show", help="Show one exact canonical P3 record.")
    literature_show.add_argument("record_id")
    literature_show.add_argument("--project-root", default=".")
    literature_show.set_defaults(handler=_literature_show)
    literature_validate = literature_commands.add_parser("validate", help="Validate chains and referenced offline artifacts.")
    literature_validate.add_argument("--project-root", default=".")
    literature_validate.set_defaults(handler=_literature_validate)
    literature_prepare = literature_commands.add_parser("prepare-emission", help="Reserve evidence before any P2 write.")
    literature_prepare.add_argument("freeze_id")
    literature_prepare.add_argument("operation_id")
    literature_prepare.add_argument("--project-root", default=".")
    literature_prepare.add_argument("--target-entry-id")
    literature_prepare.add_argument("--actor-id", required=True)
    literature_prepare.add_argument("--idempotency-key", required=True)
    literature_prepare.set_defaults(handler=_literature_prepare)
    for name, handler, help_text in (
        ("emit", _literature_emit, "Apply a prepared emission transaction."),
        ("reconcile", _literature_reconcile, "Recover and reconcile an interrupted emission transaction."),
    ):
        command = literature_commands.add_parser(name, help=help_text)
        command.add_argument("operation_id")
        command.add_argument("--project-root", default=".")
        command.add_argument("--actor-id", required=True)
        command.set_defaults(handler=handler)

    campaign = commands.add_parser("campaign", help="Expert YAML compatibility, validation, inspection, and execution.")
    campaign_commands = campaign.add_subparsers(
        dest="campaign_command",
        metavar="{show,validate,validate-mechanics,run}",
    )
    show = campaign_commands.add_parser("show", help="Show campaign source and latest run state.")
    show.add_argument("campaign_id")
    _database_argument(show)
    show.add_argument("--limit", type=int, default=10)
    show.add_argument("--explain", action="store_true", help="Resolve authored mechanics, run lineage, validation, and verdict.")
    show.add_argument("--variant", help="Select one authored variant for the explanation and latest-run lookup.")
    show.add_argument("--run", help="Select a run UID or test run ID for the explanation.")
    show.add_argument(
        "--write-card",
        nargs="?",
        const="",
        help="Write a generated Markdown run card; optionally provide an output path.",
    )
    show.add_argument("--json", action="store_true")
    show.set_defaults(handler=_campaign_show)
    new = campaign_commands.add_parser(
        "new",
        help="Deprecated engine-developer compatibility scaffold.",
        description=(
            "Deprecated engine-developer compatibility scaffold. New governed "
            "research must use CampaignDraftV1 through Studio or `alphaquest draft`."
        ),
    )
    new.add_argument("campaign_id")
    new.add_argument("--symbol", required=True, choices=("ES", "NQ"))
    new.add_argument("--edge-family", required=True)
    new.add_argument("--timeframe", default="1m")
    new.add_argument("--dataset-id")
    new.add_argument("--data-path")
    new.add_argument("--campaign-root", default="research/campaigns/active")
    new.set_defaults(handler=_campaign_new)
    # Keep old automation callable without advertising an incomplete authoring
    # path to new researchers. Strict drafts are the only supported new-work UI.
    campaign_commands._choices_actions.pop()  # type: ignore[attr-defined]
    validate = campaign_commands.add_parser("validate", help="Run fail-closed preflight on one campaign.")
    validate.add_argument("campaign_id")
    validate.add_argument("--campaign-root", default="research/campaigns/active")
    validate.add_argument("--skip-tests", action="store_true")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(handler=_campaign_validate)
    mechanics = campaign_commands.add_parser(
        "validate-mechanics",
        help="Run the declared small deterministic bar-lane mechanics-validation slice.",
    )
    mechanics.add_argument("campaign_id")
    mechanics.add_argument("--variant", required=True)
    mechanics.add_argument("--campaign-root", default="research/campaigns/active")
    mechanics.set_defaults(handler=_campaign_validate_mechanics)
    run = campaign_commands.add_parser("run", help="Run the staged workflow for one authored variant.")
    run.add_argument("campaign_id")
    run.add_argument("--variant", required=True)
    run.add_argument("--campaign-root", default="research/campaigns/active")
    run.add_argument("--skip-validation", action="store_true")
    run.add_argument("--continue-on-failure", action="store_true")
    run.add_argument("--no-acceptance", action="store_true")
    run.add_argument("--fast-runtime-defaults", action="store_true")
    run.set_defaults(handler=_campaign_run)

    data = commands.add_parser("data", help="Inspect declared datasets or local files.")
    data_commands = data.add_subparsers(dest="data_command")
    inspect = data_commands.add_parser("inspect", help="Inspect a file path or dataset ID.")
    inspect.add_argument("value")
    inspect.add_argument("--database", default=str(DEFAULT_DATABASE))
    inspect.add_argument("--json", action="store_true")
    inspect.set_defaults(handler=_data_inspect)
    data_import = data_commands.add_parser("import", help="Quarantine and govern a local CSV or Parquet dataset.")
    data_import.add_argument("source")
    data_import.add_argument("--project-root", default=".")
    data_import.add_argument("--dataset-id", required=True)
    data_import.add_argument("--symbol", required=True, choices=("ES", "NQ"))
    data_import.add_argument("--timeframe", required=True)
    data_import.add_argument("--timezone", required=True)
    data_import.add_argument("--timestamp-semantics", required=True, choices=("bar_open", "bar_close"))
    data_import.add_argument(
        "--roll-policy",
        required=True,
        choices=("single_contract", "explicit_roll_calendar"),
        help="Executable governed contract-selection rule; multi-contract files require a predeclared roll calendar.",
    )
    data_import.add_argument("--timestamp-column", default="timestamp")
    data_import.add_argument("--open-column", default="open")
    data_import.add_argument("--high-column", default="high")
    data_import.add_argument("--low-column", default="low")
    data_import.add_argument("--close-column", default="close")
    data_import.add_argument("--volume-column", default="volume")
    data_import.add_argument("--contract-column")
    data_import.add_argument("--roll-calendar", help="CSV with start_timestamp and contract_symbol columns.")
    data_import.add_argument("--single-contract", action="store_true")
    data_import.add_argument("--json", action="store_true")
    data_import.set_defaults(handler=_data_import)

    draft = commands.add_parser("draft", help="Validate or publish a Studio-authored draft.")
    draft_commands = draft.add_subparsers(dest="draft_command")
    draft_validate = draft_commands.add_parser("validate", help="Validate the strict CampaignDraftV1 contract.")
    draft_validate.add_argument("campaign_id")
    draft_validate.add_argument("--project-root", default=".")
    draft_validate.add_argument("--json", action="store_true")
    draft_validate.set_defaults(handler=_draft_validate)
    draft_publish = draft_commands.add_parser("publish", help="Compile and transactionally publish a frozen draft.")
    draft_publish.add_argument("campaign_id")
    draft_publish.add_argument("--project-root", default=".")
    draft_publish.add_argument("--json", action="store_true")
    draft_publish.set_defaults(handler=_draft_publish)

    artifacts = commands.add_parser("artifacts", help="Resolve generated evidence from the registry.")
    artifact_commands = artifacts.add_subparsers(dest="artifact_command")
    find = artifact_commands.add_parser("find", help="Find critical artifacts for a run or campaign.")
    find.add_argument("run_uid", nargs="?")
    find.add_argument("--campaign")
    _database_argument(find)
    find.add_argument("--limit", type=int, default=100)
    find.add_argument("--json", action="store_true")
    find.set_defaults(handler=_artifacts_find)

    tutorial = commands.add_parser("tutorial", help="Generate and run the synthetic onboarding campaign.")
    tutorial.add_argument("--output-root", default="examples/tutorial_campaign/generated")
    tutorial.add_argument("--no-run", action="store_true")
    tutorial.set_defaults(handler=_tutorial)

    studio = commands.add_parser("studio", help="Start or inspect the local no-code Research Studio.")
    studio_commands = studio.add_subparsers(dest="studio_command")
    studio_start = studio_commands.add_parser("start", help="Launch Research Studio on this workstation.")
    studio_start.add_argument("--project-root", default=".")
    studio_start.add_argument("--port", type=int, default=8501)
    studio_start.add_argument("--address", default="127.0.0.1")
    studio_start.add_argument("--background", action="store_true")
    studio_start.add_argument("--no-browser", action="store_true")
    studio_start.add_argument(
        "--legacy-streamlit",
        action="store_true",
        help="Use the retired Streamlit interface temporarily for compatibility.",
    )
    studio_start.add_argument("--json", action="store_true")
    studio_start.set_defaults(handler=_studio_start)
    studio_status = studio_commands.add_parser("status", help="Show Research Studio process status.")
    studio_status.add_argument("--project-root", default=".")
    studio_status.add_argument("--json", action="store_true")
    studio_status.set_defaults(handler=_studio_status)
    studio_stop = studio_commands.add_parser("stop", help="Stop the background Research Studio process.")
    studio_stop.add_argument("--project-root", default=".")
    studio_stop.add_argument("--json", action="store_true")
    studio_stop.set_defaults(handler=_studio_stop)
    studio_worker = studio_commands.add_parser("worker", help="Run the durable single local Studio worker.")
    studio_worker.add_argument("--project-root", default=".")
    studio_worker.add_argument("--once", action="store_true", help="Drain at most one job, then exit.")
    studio_worker.add_argument("--poll-interval", type=float, default=0.5)
    studio_worker.set_defaults(handler=_studio_worker)
    studio_attempt = studio_commands.add_parser(
        "attempt",
        help="Create or submit an explicit governed follow-up attempt.",
    )
    studio_attempt_commands = studio_attempt.add_subparsers(dest="studio_attempt_command")
    attempt_create = studio_attempt_commands.add_parser(
        "create",
        help="Clone every currently declared frozen definition into a new auditable attempt identity.",
    )
    attempt_create.add_argument("campaign_id")
    attempt_create.add_argument(
        "--kind",
        required=True,
        choices=(
            "replication",
            "data_refresh",
            "methodology_rerun",
            "pre_pnl_mechanics_correction",
            "pre_pnl_parameter_declaration",
            "rescue",
        ),
    )
    attempt_create.add_argument("--parent", default="original")
    attempt_create.add_argument("--reason", required=True)
    attempt_create.add_argument("--created-by", required=True)
    attempt_create.add_argument("--dataset-id")
    attempt_create.add_argument("--target-variant")
    attempt_create.add_argument("--mechanics-variant")
    attempt_create.add_argument("--mechanics-start-date")
    attempt_create.add_argument("--mechanics-end-date")
    attempt_create.add_argument(
        "--mechanics-session-count",
        type=int,
        help=(
            "Compatibility check for the fixed repository-wide mechanics session count; "
            "this cannot override policy and should normally be omitted."
        ),
    )
    attempt_create.add_argument("--component", choices=("entry", "sl", "tp"))
    attempt_create.add_argument("--parameter")
    attempt_create.add_argument("--value", help="JSON scalar for an explicit mechanics correction.")
    attempt_create.add_argument(
        "--refresh-certification",
        action="store_true",
        help=(
            "For a pre-PnL mechanics correction, bind the target variant to the current certified "
            "implementation without changing a scalar parameter."
        ),
    )
    attempt_create.add_argument(
        "--replacement-strategy-id",
        help=(
            "For a certified implementation refresh, replace the target variant's "
            "strategy package while preserving the immutable parent attempt."
        ),
    )
    attempt_create.add_argument(
        "--parameter-grid-json",
        help="JSON object of certified event parameter names to predeclared value lists.",
    )
    attempt_create.add_argument("--latest-entry-time")
    attempt_create.add_argument("--flatten-time")
    attempt_create.add_argument("--max-trades-per-day", type=int)
    attempt_create.add_argument("--authorized-by")
    attempt_create.add_argument("--project-root", default=".")
    attempt_create.add_argument("--json", action="store_true")
    attempt_create.set_defaults(handler=_studio_attempt_create)
    attempt_list = studio_attempt_commands.add_parser("list", help="List original and governed follow-up identities.")
    attempt_list.add_argument("campaign_id")
    attempt_list.add_argument("--project-root", default=".")
    attempt_list.add_argument("--json", action="store_true")
    attempt_list.set_defaults(handler=_studio_attempt_list)
    attempt_mechanics = studio_attempt_commands.add_parser(
        "queue-mechanics",
        help="Queue fresh mechanics evidence for the current sequential variant.",
    )
    attempt_mechanics.add_argument("campaign_id")
    attempt_mechanics.add_argument("attempt_id")
    attempt_mechanics.add_argument("--project-root", default=".")
    attempt_mechanics.add_argument("--json", action="store_true")
    attempt_mechanics.set_defaults(handler=_studio_attempt_queue_mechanics)
    attempt_run = studio_attempt_commands.add_parser(
        "queue-run",
        help="Queue the approved current sequential variant in one explicit attempt.",
    )
    attempt_run.add_argument("campaign_id")
    attempt_run.add_argument("attempt_id")
    attempt_run.add_argument("--project-root", default=".")
    attempt_run.add_argument("--json", action="store_true")
    attempt_run.set_defaults(handler=_studio_attempt_queue_run)

    factory = commands.add_parser(
        "factory",
        help="Operate the supervised, subscription-backed local Codex research factory.",
    )
    factory_commands = factory.add_subparsers(dest="factory_command")
    factory_status = factory_commands.add_parser("status", help="Show Codex availability and factory state.")
    factory_status.add_argument("--project-root", default=".")
    factory_status.add_argument("--campaign-id")
    factory_status.add_argument("--json", action="store_true")
    factory_status.set_defaults(handler=_factory_status)
    factory_development_status = factory_commands.add_parser(
        "development-status",
        help="Resolve the read-only development dependency roadmap.",
    )
    factory_development_status.add_argument("--project-root", default=".")
    factory_development_status.add_argument(
        "--roadmap",
        help="Roadmap JSON path; relative paths are resolved from the project root.",
    )
    factory_development_status.add_argument("--json", action="store_true")
    factory_development_status.add_argument("--check-unit")
    factory_development_status.set_defaults(handler=_factory_development_status)
    factory_tasks = factory_commands.add_parser("tasks", help="List durable Codex proposal tasks.")
    factory_tasks.add_argument("--project-root", default=".")
    factory_tasks.add_argument("--limit", type=int, default=100)
    factory_tasks.add_argument("--json", action="store_true")
    factory_tasks.set_defaults(handler=_factory_tasks)
    factory_run_next = factory_commands.add_parser(
        "run-next",
        help="Queue the next deterministic bounded AI step without invoking Codex inline.",
    )
    factory_run_next.add_argument("--project-root", default=".")
    factory_run_next.add_argument("--campaign-id")
    factory_run_next.add_argument("--request-id", required=True)
    factory_run_next.add_argument("--selected-source", help="JSON file identifying one canonical capture for proposal preparation")
    factory_run_next.add_argument("--json", action="store_true")
    factory_run_next.set_defaults(handler=_factory_run_next)
    factory_worker = factory_commands.add_parser(
        "worker",
        help="Run the separate local Codex proposal worker.",
    )
    factory_worker.add_argument("--project-root", default=".")
    factory_worker.add_argument("--once", action="store_true", help="Handle at most one task, then exit.")
    factory_worker.add_argument("--poll-interval", type=float, default=0.5)
    factory_worker.set_defaults(handler=_factory_worker)
    factory_pause = factory_commands.add_parser("pause", help="Pause new local Codex work globally.")
    factory_pause.add_argument("--project-root", default=".")
    factory_pause.add_argument("--reason", default="Paused by the local operator.")
    factory_pause.add_argument("--json", action="store_true")
    factory_pause.set_defaults(handler=_factory_pause)
    factory_resume = factory_commands.add_parser("resume", help="Resume the local Codex proposal factory.")
    factory_resume.add_argument("--project-root", default=".")
    factory_resume.add_argument("--json", action="store_true")
    factory_resume.set_defaults(handler=_factory_resume)
    factory_cancel = factory_commands.add_parser("cancel", help="Cancel one queued or running Codex task.")
    factory_cancel.add_argument("task_id")
    factory_cancel.add_argument("--project-root", default=".")
    factory_cancel.add_argument("--json", action="store_true")
    factory_cancel.set_defaults(handler=_factory_cancel)
    return parser


def _database_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))


def _strategy_list(args: argparse.Namespace) -> int:
    from alphaquest.strategy_certification import load_strategy_certifications

    records = [
        item.public_record()
        for item in load_strategy_certifications(args.project_root, require_current=False).values()
    ]
    if args.json:
        print(json.dumps(records, indent=2))
    else:
        for record in records:
            print(
                f"{record['strategy_id']} v{record['implementation_version']} "
                f"{record['certification_status']} {record['implementation_sha256']}"
            )
    return 0


def _account_list(args: argparse.Namespace) -> int:
    from alphaquest.accounts.catalog import list_account_profiles

    rows = list_account_profiles(args.project_root, novice_only=not args.all)
    _emit_rows(rows, args.json)
    return 0


def _account_assess(args: argparse.Namespace) -> int:
    from alphaquest.accounts.assessment import run_governed_account_assessment
    from alphaquest.accounts.catalog import resolve_account_profile
    from alphaquest.accounts.models import AccountAssessmentCostsV1
    from alphaquest.studio.results import RESULT_BUNDLE_V3_FILENAME, build_result_bundle_v3

    resolved = resolve_account_profile(
        args.profile_id,
        version=args.profile_version,
        project_root=args.project_root,
    )
    path = Path(args.trades).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"trade evidence is missing: {path}")
    trades = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)
    config_path = Path(args.config).resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"frozen config is missing: {config_path}")
    config_sha256 = _file_digest(config_path)

    acquisition = resolved.profile.rules.acquisition
    cost_required = (
        acquisition.evaluation_price_mode == "assessment_input_required"
        or acquisition.activation_fee_mode == "assessment_input_required"
    )
    costs = None
    if cost_required:
        missing = []
        if args.evaluation_price is None:
            missing.append("--evaluation-price")
        if acquisition.activation_fee_mode == "assessment_input_required" and args.activation_fee is None:
            missing.append("--activation-fee")
        if not args.cost_source:
            missing.append("--cost-source")
        if not args.cost_observed_at:
            missing.append("--cost-observed-at")
        if missing:
            raise ValueError("cost-adjusted account assessment requires " + ", ".join(missing))
        costs = AccountAssessmentCostsV1.model_validate(
            {
                "evaluation_purchase_price": args.evaluation_price,
                "activation_fee": args.activation_fee or 0.0,
                "other_upfront_costs": args.other_upfront_costs,
                "observed_at": args.cost_observed_at,
                "source": args.cost_source,
            },
            strict=False,
        )

    output_root = args.output_root or load_storage_layout(args.project_root).research_artifact_root
    manifest = run_governed_account_assessment(
        trades,
        resolved,
        output_root,
        campaign_id=args.campaign_id,
        variant_id=args.variant_id,
        attempt_id=args.attempt_id,
        config_sha256=config_sha256,
        data_sha256=args.data_sha256,
        strategy_implementation_sha256=args.strategy_implementation_sha256,
        costs=costs,
        manual_attestations=args.attest,
        evaluation_start=args.evaluation_start,
        evaluation_end=args.evaluation_end,
        runs=args.runs,
        seed=args.seed,
    )
    if args.result_bundle_v2:
        result_v2 = Path(args.result_bundle_v2).resolve()
        build_result_bundle_v3(
            result_v2,
            [Path(manifest["assessment_path"]) / "evaluation_manifest.json"],
            result_v2.parent / RESULT_BUNDLE_V3_FILENAME,
        )
        manifest["result_bundle_v3"] = str(result_v2.parent / RESULT_BUNDLE_V3_FILENAME)
    if args.json:
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        print(
            f"{manifest['profile_id']}@{manifest['profile_version']}: {manifest['verdict']} "
            f"({manifest['assessment_path']})"
        )
    return 0


def _strategy_audit(args: argparse.Namespace) -> int:
    from alphaquest.strategy_certification import (
        audit_strategy_certification,
        load_strategy_certifications,
    )

    certifications = load_strategy_certifications(args.project_root, require_current=False)
    if args.strategy_id:
        if args.strategy_id not in certifications:
            raise ValueError(f"strategy {args.strategy_id!r} has no certification manifest")
        certifications = {args.strategy_id: certifications[args.strategy_id]}
    records = []
    failed = False
    for item in certifications.values():
        errors = audit_strategy_certification(item, args.project_root)
        failed = failed or bool(errors)
        records.append({**item.public_record(), "verdict": "FAIL" if errors else "PASS", "errors": errors})
    if args.json:
        print(json.dumps(records, indent=2))
    else:
        for record in records:
            print(f"{record['strategy_id']}: {record['verdict']}")
            for error in record["errors"]:
                print(f"- {error}")
    return 2 if failed else 0


def _strategy_certify(args: argparse.Namespace) -> int:
    from alphaquest.strategy_certification import certify_strategy

    result = certify_strategy(args.strategy_id, args.project_root)
    payload = {**result.public_record(), "verdict": "PASS"}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(
            f"{result.strategy_id} v{result.implementation_version}: PASS "
            f"({result.implementation_sha256})"
        )
    return 0


def _studio_start(args: argparse.Namespace) -> int:
    from alphaquest.studio.launcher import start_studio

    payload = start_studio(
        project_root=args.project_root,
        port=args.port,
        address=args.address,
        background=args.background,
        open_browser=not args.no_browser,
        legacy_streamlit=args.legacy_streamlit,
    )
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_mapping(payload)
    return int(payload.get("exit_code") or 0)


def _studio_status(args: argparse.Namespace) -> int:
    from alphaquest.studio.launcher import studio_status

    payload = studio_status(project_root=args.project_root)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_mapping(payload)
    return 0


def _studio_stop(args: argparse.Namespace) -> int:
    from alphaquest.studio.launcher import stop_studio

    payload = stop_studio(project_root=args.project_root)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_mapping(payload)
    return 0


def _studio_worker(args: argparse.Namespace) -> int:
    from alphaquest.research.storage import load_storage_layout
    from alphaquest.studio.worker import run_forever

    root = Path(args.project_root).resolve()
    database = load_storage_layout(root).studio_runtime_root / "jobs.sqlite3"
    handled = run_forever(
        database,
        project_root=root,
        poll_interval=args.poll_interval,
        max_jobs=1 if args.once else None,
    )
    print(json.dumps({"worker": "stopped", "jobs_handled": handled, "database": str(database)}))
    return 0


def _studio_attempt_create(args: argparse.Namespace) -> int:
    from alphaquest.studio.followups import FollowUpAttemptRequestV1, FollowUpAttemptService

    patches = []
    patch_values = (args.component, args.parameter, args.value)
    if any(value is not None for value in patch_values):
        if args.target_variant is None or not all(value is not None for value in patch_values):
            raise ValueError(
                "mechanics changes require --target-variant, --component, --parameter, and --value together"
            )
        try:
            scalar = json.loads(args.value)
        except json.JSONDecodeError:
            scalar = args.value
        if isinstance(scalar, (dict, list)):
            raise ValueError("--value must be one JSON scalar, not an object or list")
        patches.append(
            {
                "variant_id": args.target_variant,
                "component": args.component,
                "parameter_path": args.parameter,
                "value": scalar,
            }
        )
    parameter_grid = {}
    if args.parameter_grid_json is not None:
        parameter_grid = json.loads(args.parameter_grid_json)
        if not isinstance(parameter_grid, dict):
            raise ValueError("--parameter-grid-json must decode to an object")
    mechanics_window_values = (
        args.mechanics_variant,
        args.mechanics_start_date,
        args.mechanics_end_date,
    )
    mechanics_validation_window = None
    if any(value is not None for value in mechanics_window_values):
        if not all(value is not None for value in mechanics_window_values):
            raise ValueError(
                "mechanics validation window requires --mechanics-variant, "
                "--mechanics-start-date, and --mechanics-end-date together"
            )
        mechanics_validation_window = {
            "variant_id": args.mechanics_variant,
            "start_date": args.mechanics_start_date,
            "end_date": args.mechanics_end_date,
        }
        if args.mechanics_session_count is not None:
            mechanics_validation_window["session_count"] = args.mechanics_session_count
    elif args.mechanics_session_count is not None:
        raise ValueError(
            "--mechanics-session-count requires --mechanics-variant, "
            "--mechanics-start-date, and --mechanics-end-date"
        )
    execution_values = (
        args.latest_entry_time,
        args.flatten_time,
        args.max_trades_per_day,
    )
    execution_timeline = None
    if any(value is not None for value in execution_values):
        if not all(value is not None for value in execution_values):
            raise ValueError(
                "execution timeline correction requires --latest-entry-time, "
                "--flatten-time, and --max-trades-per-day together"
            )
        execution_timeline = {
            "latest_entry_time": args.latest_entry_time,
            "flatten_time": args.flatten_time,
            "max_trades_per_day": args.max_trades_per_day,
        }
    request = FollowUpAttemptRequestV1.model_validate(
        {
            "campaign_id": args.campaign_id,
            "attempt_kind": args.kind,
            "parent_attempt_id": args.parent,
            "reason": args.reason,
            "created_by": args.created_by,
            "dataset_id": args.dataset_id,
            "target_variant_id": args.target_variant,
            "authorized_by": args.authorized_by,
            "mechanic_patches": patches,
            "refresh_certification": args.refresh_certification,
            "replacement_strategy_id": args.replacement_strategy_id,
            "parameter_grid": parameter_grid,
            "mechanics_validation_window": mechanics_validation_window,
            "execution_timeline": execution_timeline,
        }
    )
    result = FollowUpAttemptService(args.project_root).create(request)
    payload = {
        "campaign_id": result.campaign_id,
        "attempt_id": result.attempt_id,
        "attempt_kind": result.attempt_kind,
        "parent_attempt_id": result.parent_attempt_id,
        "destination": str(result.destination),
        "manifest_path": str(result.manifest_path),
        "config_paths": [str(path) for path in result.config_paths],
        "config_sha256": dict(result.config_sha256),
        "ledger_rows_appended": result.ledger_rows_appended,
        "indexes_refreshed": result.indexes_refreshed,
        "next_action": result.next_action,
        "preflight_verdict": result.preflight_verdict,
    }
    _print_studio_payload(payload, as_json=args.json)
    return 0


def _studio_attempt_list(args: argparse.Namespace) -> int:
    from alphaquest.studio.followups import FollowUpAttemptService

    payload = FollowUpAttemptService(args.project_root).list_attempts(args.campaign_id)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _emit_rows(payload, False)
    return 0


def _studio_attempt_queue_mechanics(args: argparse.Namespace) -> int:
    from alphaquest.studio.followups import FollowUpAttemptService

    jobs = FollowUpAttemptService(args.project_root).queue_mechanics_validation(
        args.campaign_id,
        args.attempt_id,
    )
    payload = [job.model_dump(mode="json", by_alias=True) for job in jobs]
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _emit_rows(payload, False)
    return 0


def _studio_attempt_queue_run(args: argparse.Namespace) -> int:
    from alphaquest.studio.followups import FollowUpAttemptService

    jobs = FollowUpAttemptService(args.project_root).queue_performance(
        args.campaign_id,
        args.attempt_id,
    )
    payload = [job.model_dump(mode="json", by_alias=True) for job in jobs]
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _emit_rows(payload, False)
    return 0


def _factory_status(args: argparse.Namespace) -> int:
    from alphaquest.studio.factory_service import ResearchFactoryService

    payload = ResearchFactoryService(args.project_root).status(campaign_id=args.campaign_id)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_mapping(payload)
    return 0


def _factory_development_status(args: argparse.Namespace) -> int:
    from alphaquest.research.development_status import load_development_status, select_development_unit

    report = load_development_status(args.project_root, args.roadmap)
    if args.check_unit is not None:
        unit = select_development_unit(report, args.check_unit)
        payload = {
            "schema": report["schema"],
            "scope_eligibility_only": True,
            "readiness_or_approval_claimed": False,
            "requested_unit_id": args.check_unit,
            "unit": unit,
            "scope_eligible": bool(unit and unit["scope_eligible"]),
        }
        exit_code = 0 if payload["scope_eligible"] else 1
    else:
        payload = report
        exit_code = 0

    if args.json:
        print(json.dumps(payload, indent=2))
    elif args.check_unit is not None:
        if payload["unit"] is None:
            print(f"UNKNOWN {args.check_unit!r}: outside the declared development scope")
        else:
            selected = payload["unit"]
            print(
                f"{selected['id']}: declared={selected['declared_status']} "
                f"effective={selected['effective_status']} scope_eligible={str(selected['scope_eligible']).lower()}"
            )
            print(f"  evidence: {json.dumps(selected['evidence'], sort_keys=True)}")
            for root_id, trigger in selected["skip_root_triggers"].items():
                print(
                    f"  blocking-root evidence {root_id}: "
                    f"{trigger['evidence_ref']} ({trigger['reason']})"
                )
            for chain in selected["skip_dependency_chains"]:
                print(f"  skip-chain: {' -> '.join(chain)}")
            for repercussion in selected["repercussions"]:
                print(f"  repercussion: {repercussion}")
    else:
        print(f"Development scope: {json.dumps(report['scope'], sort_keys=True)}")
        print("Scope eligibility only; this report makes no readiness or approval claim.")
        for unit in report["units"]:
            roots = ",".join(unit["skip_root_ids"]) or "-"
            print(
                f"{unit['id']}: declared={unit['declared_status']} "
                f"effective={unit['effective_status']} skip_roots={roots}"
            )
            print(f"  evidence: {json.dumps(unit['evidence'], sort_keys=True)}")
            for root_id, trigger in unit["skip_root_triggers"].items():
                print(
                    f"  blocking-root evidence {root_id}: "
                    f"{trigger['evidence_ref']} ({trigger['reason']})"
                )
            for chain in unit["skip_dependency_chains"]:
                print(f"  skip-chain: {' -> '.join(chain)}")
            for repercussion in unit["repercussions"]:
                print(f"  repercussion: {repercussion}")
    return exit_code


def _factory_tasks(args: argparse.Namespace) -> int:
    from alphaquest.studio.factory_service import ResearchFactoryService

    payload = ResearchFactoryService(args.project_root).list_tasks(limit=args.limit)
    if args.json:
        print(json.dumps({"tasks": payload}, indent=2))
    else:
        _emit_rows(payload, False)
    return 0


def _factory_run_next(args: argparse.Namespace) -> int:
    from alphaquest.studio.factory_service import ResearchFactoryService

    selected = json.loads(Path(args.selected_source).read_text(encoding="utf-8")) if args.selected_source else None
    task = ResearchFactoryService(args.project_root).enqueue_next(
        campaign_id=args.campaign_id,
        request_id=args.request_id,
        **({"selected_source": selected} if selected is not None else {}),
    )
    payload = {"task": task, "queued_only": True, "codex_invoked_inline": False}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_mapping(payload)
    return 0


def _factory_worker(args: argparse.Namespace) -> int:
    from alphaquest.studio.factory_service import ResearchFactoryService

    service = ResearchFactoryService(args.project_root)
    handled = service.run_worker_forever(
        poll_interval=args.poll_interval,
        max_tasks=1 if args.once else None,
    )
    print(
        json.dumps(
            {
                "worker": "stopped",
                "tasks_handled": handled,
                "database": str(service.database_path),
            }
        )
    )
    return 0


def _factory_pause(args: argparse.Namespace) -> int:
    from alphaquest.studio.factory_service import ResearchFactoryService

    payload = ResearchFactoryService(args.project_root).pause(reason=args.reason)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_mapping(payload)
    return 0


def _factory_resume(args: argparse.Namespace) -> int:
    from alphaquest.studio.factory_service import ResearchFactoryService

    payload = ResearchFactoryService(args.project_root).resume()
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_mapping(payload)
    return 0


def _factory_cancel(args: argparse.Namespace) -> int:
    from alphaquest.studio.factory_service import ResearchFactoryService

    payload = {"task": ResearchFactoryService(args.project_root).cancel(args.task_id)}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_mapping(payload)
    return 0


def _print_studio_payload(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        _print_mapping(payload)


def _draft_validate(args: argparse.Namespace) -> int:
    from alphaquest.studio.drafts import DraftStore
    from alphaquest.studio.publishing import StudioPublicationService

    store = DraftStore(args.project_root)
    report = store.validation_report(args.campaign_id)
    if report.get("valid") and report.get("frozen"):
        try:
            report["publication_preflight"] = StudioPublicationService(args.project_root).preflight_draft(
                store.validate(args.campaign_id)
            )
        except (OSError, ValueError, RuntimeError) as exc:
            report["valid"] = False
            report["errors"] = [
                {"field": "publication_preflight", "message": str(exc)}
            ]
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_mapping(report)
    return 0 if report["valid"] else 1


def _draft_publish(args: argparse.Namespace) -> int:
    from alphaquest.studio.drafts import DraftStore
    from alphaquest.studio.publishing import StudioPublicationService

    root = Path(args.project_root).resolve()
    draft = DraftStore(root).validate(args.campaign_id)
    result = StudioPublicationService(root).publish(draft)
    payload = {
        "campaign_id": result.campaign_id,
        "destination": str(result.destination),
        "files": [str(path) for path in result.files],
        "file_sha256": dict(result.file_sha256),
        "draft_sha256": result.draft_sha256,
        "ledger_rows_appended": result.ledger_rows_appended,
        "indexes_refreshed": result.indexes_refreshed,
        "journal_path": str(result.journal_path),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_mapping(payload)
    return 0


def _data_import(args: argparse.Namespace) -> int:
    from alphaquest.studio.data_import import DataImportSpec, DatasetImporter

    result = DatasetImporter(args.project_root).import_file(
        args.source,
        DataImportSpec(
            dataset_id=args.dataset_id,
            symbol=args.symbol,
            timeframe=args.timeframe,
            timezone=args.timezone,
            timestamp_semantics=args.timestamp_semantics,
            roll_policy=args.roll_policy,
            roll_calendar_path=args.roll_calendar,
            timestamp_column=args.timestamp_column,
            open_column=args.open_column,
            high_column=args.high_column,
            low_column=args.low_column,
            close_column=args.close_column,
            volume_column=args.volume_column,
            contract_column=args.contract_column,
            single_contract_confirmed=args.single_contract,
        ),
    )
    payload = {
        "manifest": result.manifest.model_dump(mode="json", by_alias=True),
        "manifest_path": str(result.manifest_path),
        "canonical_path": str(result.canonical_path),
        "quarantined_path": str(result.quarantined_path),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_mapping(payload)
    return 0 if result.manifest.quality_verdict == "PASS" else 1


def _workspace_build(args: argparse.Namespace) -> int:
    root = Path(args.project_root).resolve()
    layout = load_storage_layout(root)
    campaign_roots = [display_path(path, root) for path in layout.campaign_roots]
    evidence_roots = [display_path(path, root) for path in layout.evidence_roots]
    counts: dict[str, int] = {}
    for evidence_root in evidence_roots:
        result = backfill_run_uids(evidence_root, project_root=root, apply=True)
        for key, value in result.items():
            counts[f"uids_{key}"] = counts.get(f"uids_{key}", 0) + value
    for campaign_root in campaign_roots:
        result = write_definition_manifests(campaign_root, project_root=root, apply=True)
        for key, value in result.items():
            counts[f"definitions_{key}"] = counts.get(f"definitions_{key}", 0) + value
    counts.update(build_registry(project_root=root, campaign_roots=campaign_roots, run_roots=evidence_roots))
    counts.update({f"export_{key}": value for key, value in export_registry_csvs(project_root=root).items()})
    counts.update({f"view_{key}": value for key, value in generate_views(project_root=root).items()})
    counts.update({f"store_{key}": value for key, value in build_run_store_index(project_root=root, apply=True).items()})
    _print_mapping(counts)
    return 0


def _research_status(args: argparse.Namespace) -> int:
    database = _require_database(args.database)
    _warn_if_stale(database)
    payload = registry_summary(database)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        rows = [
            {"metric": "built_at", "value": payload.get("built_at")},
            {"metric": "campaigns", "value": payload.get("campaigns")},
            {"metric": "variants", "value": payload.get("variants")},
            {"metric": "attempts", "value": payload.get("attempts")},
            {"metric": "runs", "value": payload.get("runs")},
            {"metric": "attempt_provenance", "value": json.dumps(payload.get("attempt_provenance"), sort_keys=True)},
            {"metric": "ambiguous_attempts", "value": payload.get("ambiguous_attempts")},
            {"metric": "one_run_attempt_violations", "value": payload.get("one_run_attempt_violations")},
            {"metric": "campaign_lifecycle", "value": json.dumps(payload.get("campaign_lifecycle"), sort_keys=True)},
            {"metric": "run_verdicts", "value": json.dumps(payload.get("run_verdicts"), sort_keys=True)},
        ]
        _print_table(rows, ("metric", "value"))
    return 0


def _research_search(args: argparse.Namespace) -> int:
    database = _require_database(args.database)
    _warn_if_stale(database)
    where: list[str] = []
    params: list[Any] = []
    if args.query:
        where.append("(c.campaign_id LIKE ? OR c.title LIKE ? OR c.edge_family LIKE ?)")
        value = f"%{args.query}%"
        params.extend((value, value, value))
    if args.symbol:
        where.append("c.campaign_id LIKE ?")
        params.append(f"{args.symbol.lower()}_%")
    if args.state:
        where.append("c.lifecycle_state = ?")
        params.append(args.state)
    if args.edge_family:
        where.append("c.edge_family LIKE ?")
        params.append(f"%{args.edge_family}%")
    verdict = args.verdict.replace("_", " ") if args.verdict else None
    if verdict:
        where.append("EXISTS (SELECT 1 FROM runs r WHERE r.campaign_id = c.campaign_id AND r.verdict = ?)")
        params.append(verdict)
    if args.failed_stage:
        where.append("EXISTS (SELECT 1 FROM runs r WHERE r.campaign_id = c.campaign_id AND r.failed_stage = ?)")
        params.append(args.failed_stage)
    if args.since:
        where.append("EXISTS (SELECT 1 FROM runs r WHERE r.campaign_id = c.campaign_id AND r.updated_at >= ?)")
        params.append(args.since)
    clause = " WHERE " + " AND ".join(where) if where else ""
    query = (
        "SELECT c.campaign_id, c.lifecycle_state, c.edge_family, c.run_count, "
        "c.latest_updated_at, c.definition_path FROM campaigns c"
        f"{clause} ORDER BY COALESCE(c.latest_updated_at, '') DESC, c.campaign_id LIMIT ?"
    )
    params.append(max(1, args.limit))
    rows = _query(database, query, params)
    _emit_rows(rows, args.json)
    return 0


def _edge_capture_observation(args: argparse.Namespace) -> int:
    from alphaquest.research.edge_backlog import EdgeBacklogStore

    record = EdgeBacklogStore(args.project_root).capture_observation(
        _edge_input(args.input),
        actor_id=args.actor_id,
        task_id=args.task_id,
    )
    _edge_json(record.model_dump(mode="json", by_alias=True))
    return 0


def _edge_revise_observation(args: argparse.Namespace) -> int:
    from alphaquest.research.edge_backlog import EdgeBacklogStore

    record = EdgeBacklogStore(args.project_root).revise_observation(
        args.observation_id,
        _edge_input(args.input),
        actor_id=args.actor_id,
        task_id=args.task_id,
    )
    _edge_json(record.model_dump(mode="json", by_alias=True))
    return 0


def _edge_create(args: argparse.Namespace) -> int:
    from alphaquest.research.edge_backlog import EdgeBacklogStore

    record = EdgeBacklogStore(args.project_root).create_entry(
        _edge_input(args.input),
        actor_id=args.actor_id,
        task_id=args.task_id,
    )
    _edge_json(record.model_dump(mode="json", by_alias=True))
    return 0


def _edge_revise(args: argparse.Namespace) -> int:
    from alphaquest.research.edge_backlog import EdgeBacklogStore

    record = EdgeBacklogStore(args.project_root).revise_entry(
        args.entry_id,
        _edge_input(args.input),
        actor_id=args.actor_id,
        task_id=args.task_id,
    )
    _edge_json(record.model_dump(mode="json", by_alias=True))
    return 0


def _edge_list(args: argparse.Namespace) -> int:
    from alphaquest.research.edge_backlog import EdgeBacklogStore

    rows = EdgeBacklogStore(args.project_root).list_entries()
    if args.state:
        rows = [row for row in rows if row["state"] == args.state]
    _emit_rows(rows, args.json)
    return 0


def _edge_show(args: argparse.Namespace) -> int:
    from alphaquest.research.edge_backlog import EdgeBacklogStore

    payload = EdgeBacklogStore(args.project_root).show(args.entry_id)
    if args.json:
        _edge_json(payload)
    else:
        _print_mapping(
            {
                "entry_id": payload["entry"]["entry_id"],
                "revision": payload["entry"]["revision"],
                "state": payload["state"],
                "title": payload["display_label"],
                "decisions": len(payload["decisions"]),
                "links": len(payload["links"]),
            }
        )
    return 0


def _edge_search(args: argparse.Namespace) -> int:
    from alphaquest.research.edge_backlog import EdgeBacklogStore

    rows = EdgeBacklogStore(args.project_root).search(args.query, state=args.state)
    _emit_rows(rows, args.json)
    return 0


def _edge_duplicate_candidates(args: argparse.Namespace) -> int:
    from alphaquest.research.edge_backlog import EdgeBacklogStore

    _edge_json(EdgeBacklogStore(args.project_root).duplicate_snapshot(args.entry_id))
    return 0


def _edge_review(args: argparse.Namespace) -> int:
    from alphaquest.research.edge_backlog import EdgeBacklogStore

    record = EdgeBacklogStore(args.project_root).record_human_decision(
        args.entry_id,
        disposition=args.disposition,
        duplicate_resolution=args.duplicate_resolution,
        candidate_snapshot_sha256=args.candidate_snapshot_sha256,
        canonical_entry_id=args.canonical_entry_id,
        related_edge_family_ids=args.related_edge_family_id,
        reason_codes=args.reason_code,
        rationale=args.rationale,
        revisit_conditions=args.revisit_condition,
        reviewer_id=args.reviewer_id,
        decision_id=args.decision_id,
    )
    _edge_json(record.model_dump(mode="json", by_alias=True))
    return 0


def _edge_resume(args: argparse.Namespace) -> int:
    from alphaquest.research.edge_backlog import EdgeBacklogStore

    record = EdgeBacklogStore(args.project_root).resume_entry(
        args.entry_id,
        reason_codes=args.reason_code,
        rationale=args.rationale,
        reviewer_id=args.reviewer_id,
        decision_id=args.decision_id,
    )
    _edge_json(record.model_dump(mode="json", by_alias=True))
    return 0


def _edge_validate(args: argparse.Namespace) -> int:
    from alphaquest.research.edge_backlog import EdgeBacklogStore

    store = EdgeBacklogStore(args.project_root)
    payload = store.validate()
    if store.layout.edge_backlog_history_index.is_file():
        payload["historical_index"] = {"status": "PRESENT_NON_AUTHORITATIVE"}
    else:
        payload["historical_index"] = {"status": "NOT_BUILT"}
    _edge_json(payload)
    return 0


def _edge_bootstrap(args: argparse.Namespace) -> int:
    from alphaquest.research.edge_backlog_bootstrap import build_historical_edge_index

    _edge_json(build_historical_edge_index(args.project_root))
    return 0


def _edge_input(value: str | Path) -> dict[str, Any]:
    path = Path(value)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read Edge Backlog JSON input {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Edge Backlog JSON input must be an object")
    return payload


def _edge_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))


def _literature_openalex_run(args: argparse.Namespace) -> int:
    from alphaquest.research.literature.stage2_runner import run_openalex_pilot

    result = run_openalex_pilot(args.project_root, args.protocol_revision_sha)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["complete"] else 2


def _literature_actor(args: argparse.Namespace):
    from alphaquest.research.literature.contracts import ActorProvenanceV1

    return ActorProvenanceV1(
        actor_class=getattr(args, "actor_class", "ALPHAQUEST_DETERMINISTIC_ENGINE"),
        actor_id=args.actor_id,
        task_id=getattr(args, "task_id", None),
    )


def _literature_put_artifact(args: argparse.Namespace) -> int:
    from alphaquest.research.literature.store import LiteratureStore

    digest = LiteratureStore(args.project_root).put_artifact(Path(args.input).read_bytes(), kind=args.kind)
    _edge_json({"kind": args.kind, "sha256": digest})
    return 0


def _literature_append(args: argparse.Namespace) -> int:
    from alphaquest.research.literature.store import LiteratureStore

    store = LiteratureStore(args.project_root)
    payload = _edge_input(args.input)
    kwargs = {"actor": _literature_actor(args), "idempotency_key": args.idempotency_key}
    if args.family == "search-finish":
        search_run_id = str(payload.pop("search_run_id"))
        record = store.finish_search(search_run_id, payload, **kwargs)
    else:
        methods = {
            "protocol": store.append_protocol,
            "search-start": store.start_search,
            "work": store.append_work,
            "source-version": store.append_source_version,
            "source-relationship": store.append_source_relationship,
            "capture": store.append_capture,
            "claim": store.append_claim,
            "evidence-relation": store.append_evidence_relation,
            "dossier": store.append_dossier,
            "freeze": store.freeze_dossier,
            "codex-attempt": store.append_codex_attempt,
        }
        record = methods[args.family](payload, **kwargs)
    _edge_json(record.model_dump(mode="json", by_alias=True))
    return 0


def _literature_list(args: argparse.Namespace) -> int:
    from alphaquest.research.literature.store import LiteratureStore

    records = LiteratureStore(args.project_root).records()
    rows = [
        {
            "append_sequence": item.append_sequence,
            "family": type(item).family,
            "record_id": item.record_id,
            "record_sha256": item.record_sha256,
        }
        for item in records
        if args.family is None or type(item).family == args.family
    ]
    _edge_json(rows)
    return 0


def _literature_show(args: argparse.Namespace) -> int:
    from alphaquest.research.literature.store import LiteratureStore

    record = LiteratureStore(args.project_root).get(args.record_id)
    _edge_json(record.model_dump(mode="json", by_alias=True))
    return 0


def _literature_validate(args: argparse.Namespace) -> int:
    from alphaquest.research.literature.store import LiteratureStore

    _edge_json(LiteratureStore(args.project_root).validate())
    return 0


def _literature_prepare(args: argparse.Namespace) -> int:
    from alphaquest.research.literature.emission import prepare_emission

    record = prepare_emission(
        args.project_root,
        freeze_id=args.freeze_id,
        operation_id=args.operation_id,
        target_entry_id=args.target_entry_id,
        actor=_literature_actor(args),
        idempotency_key=args.idempotency_key,
    )
    _edge_json(record.model_dump(mode="json", by_alias=True))
    return 0


def _literature_emit(args: argparse.Namespace) -> int:
    from alphaquest.research.literature.emission import emit_prepared

    record = emit_prepared(
        args.project_root,
        operation_id=args.operation_id,
        actor=_literature_actor(args),
    )
    _edge_json(record.model_dump(mode="json", by_alias=True))
    return 0


def _literature_reconcile(args: argparse.Namespace) -> int:
    from alphaquest.research.literature.emission import reconcile_emission

    record = reconcile_emission(
        args.project_root,
        operation_id=args.operation_id,
        actor=_literature_actor(args),
    )
    _edge_json(record.model_dump(mode="json", by_alias=True))
    return 0


def _campaign_show(args: argparse.Namespace) -> int:
    database = _require_database(args.database)
    if args.explain or args.write_card is not None or args.variant or args.run:
        from alphaquest.research.explain import explain_research, explanation_markdown

        payload = explain_research(
            args.campaign_id,
            database_path=database,
            variant_id=args.variant,
            run_id=args.run,
        )
        markdown = explanation_markdown(payload)
        if args.write_card is not None:
            run = payload.get("run") or {}
            default_name = str(run.get("run_uid") or args.campaign_id)
            card_path = Path(args.write_card) if args.write_card else Path("views/run_cards") / f"{default_name}.md"
            card_path.parent.mkdir(parents=True, exist_ok=True)
            card_path.write_text(markdown, encoding="utf-8")
            payload["run_card_path"] = str(card_path)
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(markdown)
        return 0
    campaign_rows = _query(database, "SELECT * FROM campaigns WHERE campaign_id = ?", [args.campaign_id])
    if not campaign_rows:
        raise ValueError(f"unknown campaign: {args.campaign_id}")
    variants = _query(
        database,
        "SELECT variant_id, symbol, timeframe, dataset_id, definition_path FROM variants "
        "WHERE campaign_id = ? ORDER BY variant_id",
        [args.campaign_id],
    )
    runs = _query(
        database,
        "SELECT run_uid, variant_id, test_run_id, verdict, failed_stage, updated_at, summary_path "
        "FROM runs WHERE campaign_id = ? ORDER BY COALESCE(updated_at, '') DESC LIMIT ?",
        [args.campaign_id, max(1, args.limit)],
    )
    payload = {"campaign": campaign_rows[0], "variants": variants, "latest_runs": runs}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_mapping(payload["campaign"])
        print("\nVariants")
        _print_table(variants, ("variant_id", "symbol", "timeframe", "dataset_id", "definition_path"))
        print("\nLatest runs")
        _print_table(runs, ("run_uid", "variant_id", "test_run_id", "verdict", "failed_stage", "updated_at"))
    return 0


def _campaign_new(args: argparse.Namespace) -> int:
    if re.fullmatch(r"[a-z0-9][a-z0-9_]*", args.campaign_id) is None:
        raise ValueError("campaign ID must contain only lowercase letters, digits, and underscores")
    campaign_root = Path(args.campaign_root)
    campaign_dir = campaign_root / args.campaign_id
    if campaign_dir.exists():
        raise ValueError(f"campaign already exists: {campaign_dir}")
    dataset_id = args.dataset_id or f"{args.campaign_id}_{args.timeframe}_dataset"
    data_path = args.data_path or f"data/raw/{args.symbol}/{args.symbol.lower()}_{args.timeframe}.csv"
    campaign_dir.mkdir(parents=True)
    campaign = {
        "campaign_id": args.campaign_id,
        "title": args.campaign_id.replace("_", " ").title(),
        "status": "authored_for_testing",
        "created_at": datetime.now(timezone.utc).date().isoformat(),
        "instrument": args.symbol,
        "timeframe": args.timeframe,
        "governance_contract_version": 2,
        "edge_family": args.edge_family,
        "hypothesis": "TODO: state the market behavior, mechanism, and falsifiable expectation.",
        "economic_edge_fingerprint": {
            "market_behavior": "TODO: identify the repeatable market behavior without implementation labels.",
            "causal_mechanism": "TODO: explain why counterparties or market structure should create the behavior.",
            "signal_inputs": "TODO: list the economically meaningful inputs, not parameter names.",
            "market_context": "TODO: state the instrument, session, and regime where the mechanism should apply.",
            "holding_period": "TODO: state the expected economic horizon from signal to exit.",
        },
        "duplicate_edge_review": {
            "reviewed_campaign_ids": [],
            "ledger_queries": ["TODO: record the research_ledger.csv query used before scaffolding."],
            "conclusion": "needs_review",
            "substantive_distinction": "TODO: explain in at least 80 characters why this is economically distinct from prior campaigns.",
        },
        "sources": [
            {
                "title": "TODO",
                "authors": "TODO",
                "year": "TODO",
                "link": "TODO",
                "relevance": "TODO: explain why this source supports the edge.",
            }
        ],
        "variants": [f"v{index:02d}" for index in range(1, 6)],
        "variant_distinctions": {
            f"v{index:02d}": {
                "mechanic": "TODO: predeclare this variant's invariant entry, risk, and exit expression.",
                "material_difference": "TODO: explain how this mechanic differs economically from the other four variants.",
            }
            for index in range(1, 6)
        },
        "rescue_policy": {"allowed": False, "max_rescues_per_failed_variant": 1},
    }
    _write_yaml(campaign_dir / "campaign.yaml", campaign)
    for index in range(1, 6):
        variant_id = f"v{index:02d}"
        variant_dir = campaign_dir / "variants" / variant_id
        variant_dir.mkdir(parents=True)
        _write_yaml(
            variant_dir / "config.yaml",
            _variant_scaffold(args, dataset_id=dataset_id, data_path=data_path, variant_id=variant_id),
        )
        modules_dir = variant_dir / "strategy_modules"
        modules_dir.mkdir()
        (modules_dir / "README.md").write_text(
            "# Strategy Modules\n\nRecord the entry, stop, target, and timeframe rationale for this variant.\n",
            encoding="utf-8",
        )
        for filename, binding in (("entry.py", "ENTRY_MODULE"), ("stop.py", "STOP_MODULE"), ("target.py", "TARGET_MODULE")):
            (modules_dir / filename).write_text(
                f'"""Bind this variant to its reviewed strategy module."""\n\n{binding} = None\n',
                encoding="utf-8",
            )
        validation_dir = variant_dir / "validation"
        validation_dir.mkdir()
        (validation_dir / "approval.template.json").write_text(
            json.dumps(_validation_approval_template(args, variant_id), indent=2) + "\n",
            encoding="utf-8",
        )
    print(campaign_dir)
    print("Complete TODO fields and strategy modules, then run `alphaquest campaign validate`.")
    return 0


def _variant_scaffold(args: argparse.Namespace, *, dataset_id: str, data_path: str, variant_id: str) -> dict[str, Any]:
    data_key = "raw_parquet" if data_path.endswith(".parquet") else "raw_csv"
    return {
        "campaign_id": args.campaign_id,
        "variant_id": variant_id,
        "attempt_id": "original",
        "attempt_kind": "original",
        "attempt_provenance": "authored",
        "strategy_name": variant_id,
        "symbol": args.symbol,
        "dataset_id": dataset_id,
        "timeframe": args.timeframe,
        "research_metadata": {
            "mechanics_review_required": True,
            "mechanics_review_version": 1,
            "mechanics_review": {
                "mechanic_expresses_edge": "TODO: explain in at least 80 characters how this variant expresses the campaign edge.",
                "entry_logic_rationale": "TODO: explain in at least 80 characters why the entry is causal, testable, and economically justified.",
                "stop_loss_rationale": "TODO: explain in at least 80 characters why this stop represents mechanical invalidation.",
                "target_exit_rationale": "TODO: explain in at least 80 characters why the target and flatten rules fit the edge.",
                "profitability_rationale": "TODO: explain in at least 80 characters why the expected payoff may survive modeled costs.",
                "known_failure_modes": "TODO: explain in at least 80 characters how this edge may fail or become unstable.",
                "pre_test_decision": "needs_completion",
            },
            "validation_gate": {
                "required": True,
                "lane": "bar",
                "data_subset": {"start_date": "TODO", "end_date": "TODO"},
                "evidence_dir": (
                    f"{CAMPAIGN_REPORT_ROOT}/{args.campaign_id}/{variant_id}/{args.symbol}/"
                    "mechanics_validation/validation_runs/core"
                ),
                "approval_path": (
                    f"research_artifacts/validation_approvals/{args.campaign_id}/{variant_id}/approval.json"
                ),
            },
        },
        "data": {
            "dataset_id": dataset_id,
            "source": "parquet" if data_key == "raw_parquet" else "csv",
            data_key: data_path,
            "symbol": args.symbol,
            "timezone": "America/New_York",
            "exchange_timezone": "America/New_York",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "point_value": 50.0 if args.symbol == "ES" else 20.0,
            "tick_value": 12.5 if args.symbol == "ES" else 5.0,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "flatten_time": "15:55:00",
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
        },
        "apex_rules": {
            "enabled": True,
            "force_flatten_enabled": True,
            "force_flatten_time": "15:55:00",
            "latest_flat_time": "15:56:00",
            "latest_entry_time": "15:45:00",
            "no_overnight_positions": True,
        },
        "strategy": {
            "entry": {"module": "TODO_entry_module", "params": {}},
            "sl": {"module": "TODO_stop_module", "params": {}},
            "tp": {"module": "TODO_target_module", "params": {}},
            "flatten_time": "15:55:00",
        },
        "test_run_id": "run1",
    }


def _validation_approval_template(args: argparse.Namespace, variant_id: str) -> dict[str, Any]:
    from alphaquest.validation.promotion_gate import (
        REQUIRED_SAMPLE_CATEGORIES,
        SAMPLING_POLICY_SHA256,
        SAMPLING_POLICY_VERSION,
    )

    return {
        "schema": "alphaquest.validation-approval/v1",
        "status": "needs_review",
        "reviewer": "",
        "reviewed_at": "",
        "notes": "",
        "campaign_id": args.campaign_id,
        "variant_id": variant_id,
        "lane": "bar",
        "config_hash": "",
        "input_data_hash": "",
        "validation_schema_version": "1.4",
        "sampled_trade_ids": [],
        "sampling_categories": {name: [] for name in REQUIRED_SAMPLE_CATEGORIES},
        "sampling_reasons": {},
        "sampling_policy_version": SAMPLING_POLICY_VERSION,
        "sampling_policy_sha256": SAMPLING_POLICY_SHA256,
    }


def _campaign_validate(args: argparse.Namespace) -> int:
    from alphaquest.research.preflight import run_preflight

    campaign_dir = Path(args.campaign_root) / args.campaign_id
    configs = _campaign_configs(campaign_dir)
    result = run_preflight(config_paths=configs, run_tests=not args.skip_tests)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("PASS" if result["passed"] else "FAIL")
        print(f"Configs checked: {len(result['configs_checked'])}")
        print(f"Distinct data sources: {result['data_sources_checked']}")
        for warning in result["warnings"][:20]:
            print(f"WARNING: {warning}")
        if len(result["warnings"]) > 20:
            print(f"WARNING: {len(result['warnings']) - 20} additional warnings; use --json for all details.")
        for failure in result["failures"]:
            print(f"FAIL: {failure}")
    return 0 if result["passed"] else 1


def _campaign_validate_mechanics(args: argparse.Namespace) -> int:
    config = Path(args.campaign_root) / args.campaign_id / "variants" / args.variant / "config.yaml"
    if not config.is_file():
        raise FileNotFoundError(f"variant config not found: {config}")
    result = subprocess.run(
        [sys.executable, "-m", "alphaquest.run_core", "--config", str(config), "--mechanics-validation"],
        check=False,
    )
    return int(result.returncode)


def _campaign_run(args: argparse.Namespace) -> int:
    config = Path(args.campaign_root) / args.campaign_id / "variants" / args.variant / "config.yaml"
    if not config.is_file():
        raise FileNotFoundError(f"variant config not found: {config}")
    summary = run_campaign_stage_tests(
        config,
        skip_validation=args.skip_validation,
        continue_on_failure=args.continue_on_failure,
        include_acceptance=not args.no_acceptance,
        fast_runtime_defaults=args.fast_runtime_defaults,
    )
    print(json.dumps({key: summary.get(key) for key in ("run_uid", "campaign_id", "variant_id", "test_run_id", "passed", "halted", "output_dir")}, indent=2))
    return 0 if summary.get("passed") else 1


def _data_inspect(args: argparse.Namespace) -> int:
    path = Path(args.value)
    if path.exists():
        payload = _inspect_path(path)
    else:
        database = _require_database(args.database)
        rows = _query(
            database,
            "SELECT campaign_id, variant_id, dataset_id, symbol, timeframe, definition_path "
            "FROM variants WHERE dataset_id = ? ORDER BY campaign_id, variant_id",
            [args.value],
        )
        if not rows:
            raise ValueError(f"no local path or registered dataset found: {args.value}")
        payload = {"dataset_id": args.value, "definitions": rows}
    if args.json:
        print(json.dumps(payload, indent=2))
    elif isinstance(payload, dict) and "definitions" in payload:
        _print_table(payload["definitions"], tuple(payload["definitions"][0]))
    else:
        _print_mapping(payload)
    return 0


def _inspect_path(path: Path) -> dict[str, Any]:
    stat = path.stat()
    payload: dict[str, Any] = {
        "path": str(path),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }
    if path.suffix.lower() == ".parquet":
        import pyarrow.parquet as pq

        parquet = pq.ParquetFile(path)
        payload.update({"format": "parquet", "rows": parquet.metadata.num_rows, "columns": parquet.schema.names})
    elif path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            payload.update({"format": "csv", "columns": next(reader, [])})
    else:
        payload["format"] = path.suffix.lower().lstrip(".") or "unknown"
    return payload


def _artifacts_find(args: argparse.Namespace) -> int:
    if not args.run_uid and not args.campaign:
        raise ValueError("provide a run UID or --campaign")
    database = _require_database(args.database)
    where = "a.run_uid = ?" if args.run_uid else "r.campaign_id = ?"
    value = args.run_uid or args.campaign
    rows = _query(
        database,
        "SELECT r.run_uid, r.campaign_id, r.variant_id, r.test_run_id, r.verdict, "
        "a.artifact_kind, a.path, a.sha256 FROM artifacts a JOIN runs r ON r.run_uid = a.run_uid "
        f"WHERE {where} ORDER BY r.updated_at DESC, a.artifact_kind LIMIT ?",
        [value, max(1, args.limit)],
    )
    _emit_rows(rows, args.json)
    return 0


def _tutorial(args: argparse.Namespace) -> int:
    from alphaquest.tutorial import run_tutorial

    result = run_tutorial(output_root=args.output_root, execute=not args.no_run)
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "PASS" else 1


def _campaign_configs(campaign_dir: Path) -> list[Path]:
    if not campaign_dir.is_dir():
        raise FileNotFoundError(f"campaign not found: {campaign_dir}")
    paths = [
        *campaign_dir.glob("variants/*/config.yaml"),
        *campaign_dir.glob("rescue_attempts/*/*/config.yaml"),
    ]
    if not paths:
        raise FileNotFoundError(f"no authored configs found: {campaign_dir}")
    return sorted(paths)


def _require_database(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_file():
        raise FileNotFoundError(f"registry missing: {path}; run `alphaquest workspace build`")
    return path


def _query(database: Path, query: str, params: Iterable[Any]) -> list[dict[str, Any]]:
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(query, tuple(params)).fetchall()]


def _emit_rows(rows: list[dict[str, Any]], as_json: bool) -> None:
    if as_json:
        print(json.dumps(rows, indent=2))
    elif rows:
        _print_table(rows, tuple(rows[0]))
    else:
        print("No matching records.")


def _print_mapping(payload: dict[str, Any]) -> None:
    _print_table([{"field": key, "value": _display_value(value)} for key, value in payload.items()], ("field", "value"))


def _print_table(rows: Iterable[dict[str, Any]], columns: tuple[str, ...]) -> None:
    rows = list(rows)
    widths = {column: len(column) for column in columns}
    for row in rows:
        for column in columns:
            widths[column] = min(60, max(widths[column], len(_display_value(row.get(column)))))
    print("  ".join(column.ljust(widths[column]) for column in columns))
    print("  ".join("-" * widths[column] for column in columns))
    for row in rows:
        print("  ".join(_display_value(row.get(column))[: widths[column]].ljust(widths[column]) for column in columns))


def _display_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value).replace("\n", " ")


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120), encoding="utf-8")


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _warn_if_stale(database: Path) -> None:
    database_mtime = database.stat().st_mtime
    layout = load_storage_layout()
    candidates = []
    for campaign_root in layout.campaign_roots:
        candidates.extend(campaign_root.glob("*/campaign.yaml"))
        candidates.extend(campaign_root.glob("*/variants/*/config.yaml"))
    for evidence_root in layout.evidence_roots:
        candidates.extend(evidence_root.glob("*/*/*/*/campaign_test_summary.json"))
        candidates.extend(evidence_root.glob("*/*/*/*/variant_test_summary.json"))
    latest = max((path.stat().st_mtime for path in candidates if path.is_file()), default=0.0)
    if latest > database_mtime:
        print("WARNING: registry is older than authored campaign source; run `alphaquest workspace build`.", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
