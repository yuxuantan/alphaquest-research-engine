"""FastAPI contract for the local AlphaQuest Research Studio.

This module contains transport concerns only.  It delegates every mutation to
the existing governed services so the React client cannot bypass publication,
approval, lineage, or one-run-per-attempt controls.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
from time import monotonic
from typing import Any, Literal, Mapping
from uuid import uuid4
import zipfile

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError as PydanticValidationError
import yaml

from alphaquest.authoring.catalog import get_certified_module_catalog
from alphaquest.authoring.models import (
    EconomicEdgeFingerprintV1,
    ExecutionSettingsV1,
    ResearchObjectivesV1,
    ResearchSourceV1,
)
from alphaquest.execution_certification import list_execution_profiles
from alphaquest.prop.profiles import list_prop_profiles
from alphaquest.accounts.catalog import list_account_profiles
from alphaquest.accounts.assessment import account_suitability_row
from alphaquest.research.campaign_stages import DEFAULT_STAGE_ORDER, STAGE_LABELS
from alphaquest.research.experiment_registry import (
    AttemptFinalizationRecovery,
    ExperimentRegistry,
    ExperimentRegistryError,
)
from alphaquest.research.storage import (
    load_storage_layout,
    resolve_campaign_context,
    resolve_recorded_path,
)
from alphaquest.studio.data_import import DataImportSpec, DatasetImporter
from alphaquest.studio.analysis import (
    governed_chart_snapshot,
    governed_dataset_scan,
    research_capability_matrix,
)
from alphaquest.studio.chart_reconciliation import reconcile_chart_export
from alphaquest.studio.finalization import FinalizationError, RunFinalizer, inspect_finalized_result
from alphaquest.studio.followups import FollowUpAttemptRequestV1, FollowUpAttemptService
from alphaquest.studio.forward_incubation import ForwardIncubationService
from alphaquest.studio.forward_reconciliation import reconcile_forward_trade_csv
from alphaquest.studio.jobs import OperationalState, SQLiteJobQueue
from alphaquest.studio.portfolio import (
    AccountContractLimitsV1,
    CandidateEvidencePaths,
    DeploymentCandidateRequest,
    DeploymentDecisionService,
    DeploymentMonitoringService,
    DeploymentDecisionV1,
    MonitoringThresholdsV1,
    PortfolioReviewV1,
    PortfolioReviewService,
)
from alphaquest.studio.results import RESULT_BUNDLE_FILENAME, ResultBundleV2
from alphaquest.studio.settings import StudioSettings, load_settings, save_settings
from alphaquest.studio.workflow import StudioWorkflowService
from alphaquest.studio.workflow_diagnostics import (
    dataset_readiness_forecast,
    global_next_actions,
    workload_forecast,
    workspace_diagnostics,
)
from alphaquest.studio.workspace import (
    list_dataset_manifests,
    list_published_campaigns,
    list_review_queue,
    refresh_generated_indexes_if_stale,
)


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateDraftRequest(APIModel):
    campaign_id: str
    title: str
    instrument: Literal["ES", "NQ"]
    research_objectives: ResearchObjectivesV1 | None = None


class BriefRequest(APIModel):
    research_objectives: ResearchObjectivesV1
    title: str
    edge_family: str
    timeframe: Literal["1m", "5m", "15m"]
    hypothesis: str
    expected_mechanism: str
    holding_horizon: str
    known_failure_modes: list[str]
    source: ResearchSourceV1
    economic_edge_fingerprint: EconomicEdgeFingerprintV1


class DuplicateReviewRequest(APIModel):
    reviewed_campaign_ids: list[str] = Field(default_factory=list)
    conclusion: Literal["distinct", "duplicate", "needs_review"]
    substantive_distinction: str


class DatasetSelectRequest(APIModel):
    dataset_id: str


class ExecutionRequest(APIModel):
    execution: ExecutionSettingsV1
    roll_policy_confirmed: bool


class RecipeRequest(APIModel):
    recipe: str
    confirmed: bool


class RuleRequest(APIModel):
    rule: dict[str, Any]


class EventStrategyRequest(APIModel):
    strategy_id: str
    confirmed: bool


class HandoffRequest(APIModel):
    reason_unsupported: str
    causal_timeline: list[str]
    required_data_granularity: str
    fill_and_ambiguity_rules: list[str]
    required_module_contract: list[str]
    required_tests: list[str]
    proposed_mechanics: list[str]


class VariantsRequest(APIModel):
    variants: list[dict[str, Any]]


class ConfirmationRequest(APIModel):
    confirmed: bool


class RevisionRequest(APIModel):
    revision_id: str
    reason: str


class AttemptRequest(APIModel):
    attempt_id: str = "original"


class StrategyCertificationRunRequest(APIModel):
    request_id: str = Field(min_length=8, max_length=120)


class AccountAssessmentRunRequest(APIModel):
    attempt_id: str = Field(min_length=1)
    variant_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    profile_version: str = Field(min_length=1)
    evaluation_purchase_price: float | None = Field(default=None, ge=0)
    activation_fee: float | None = Field(default=None, ge=0)
    other_upfront_costs: float = Field(default=0.0, ge=0)
    cost_observed_at: datetime | None = None
    cost_source: str | None = None
    manual_attestations: list[str] = Field(default_factory=list)


class NextVariantRequest(APIModel):
    variant: dict[str, Any]
    failure_analysis: str = Field(min_length=80)
    created_by: str = Field(min_length=1)


class ImportDatasetRequest(APIModel):
    upload_token: str
    spec: "BrowserDataImportSpec"
    roll_calendar_upload_token: str | None = None


class BrowserDataImportSpec(APIModel):
    """Import declarations that never accept an arbitrary workstation path."""

    dataset_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_]*$")
    symbol: Literal["ES", "NQ"]
    timeframe: str = Field(pattern=r"^[1-9]\d*[mhd]$")
    timezone: str
    exchange_timezone: str = "America/New_York"
    timestamp_semantics: Literal["bar_open", "bar_close"]
    session_template_id: Literal[
        "cme_us_equity_rth",
        "cme_us_equity_morning",
    ] | None = None
    roll_policy: Literal["single_contract", "explicit_roll_calendar"]
    timestamp_column: str
    open_column: str
    high_column: str
    low_column: str
    close_column: str
    volume_column: str
    contract_column: str | None = None
    single_contract_confirmed: bool = False


class TutorialRequest(APIModel):
    reset: bool = True


class MechanicsAnnotationRequest(APIModel):
    campaign_id: str
    attempt_id: str = "original"
    variant_id: str
    trade_id: str | int
    evidence_token: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewer_status: Literal[
        "Correct",
        "Bug suspected",
        "Data issue",
        "Needs deeper review",
        "False signal",
        "Exit issue",
        "Orderflow filter issue",
    ]
    reviewer_notes: str = ""


class MechanicsDecisionRequest(APIModel):
    campaign_id: str
    attempt_id: str = "original"
    variant_id: str
    decision: Literal["approve", "reject"]
    reviewer: str
    notes: str


class MechanicsReconciliationRequest(APIModel):
    campaign_id: str
    attempt_id: str = "original"
    variant_id: str
    upload_token: str = Field(pattern=r"^[a-f0-9]{32}$")


class CandidateDecisionRequest(APIModel):
    review_id: str
    evidence_token: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewer: str
    decision: Literal["approved_candidate", "rejected", "needs_manual_review"]
    notes: str


class ForwardIncubationStartRequest(APIModel):
    campaign_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_]*$")
    variant_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_]*$")
    attempt_id: str = Field(default="original", pattern=r"^[a-z0-9][a-z0-9_]*$")
    created_by: str = Field(min_length=1)


class ForwardIncubationObservationRequest(APIModel):
    recorded_by: str = Field(min_length=1)
    notes: str = Field(min_length=1)
    upload_token: str = Field(pattern=r"^[a-f0-9]{32}$")
    trade_count_delta: int = Field(ge=0)
    net_pnl_delta: float
    prop_rule_breach: bool
    forced_flatten_violation: bool
    triggered_abandonment_rules: list[str] = Field(default_factory=list)


class ForwardIncubationReviewRequest(APIModel):
    reviewer: str = Field(min_length=1)
    notes: str = Field(min_length=1)
    upload_token: str = Field(pattern=r"^[a-f0-9]{32}$")
    decision: Literal["continue", "fail", "needs_manual_review"]


class ForwardIncubationRetireRequest(APIModel):
    retired_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class PortfolioReviewCreateRequest(APIModel):
    candidate_ids: list[str] = Field(min_length=2)
    minimum_common_sessions: int = Field(default=20, ge=2)


class DeploymentCandidateSelectionRequest(APIModel):
    candidate_id: str
    attempt_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_]*$")
    requested_contracts: int = Field(ge=1)


class DeploymentDecisionCreateRequest(APIModel):
    candidates: list[DeploymentCandidateSelectionRequest] = Field(min_length=1)
    portfolio_review_id: str | None = None
    account_limits: AccountContractLimitsV1
    rollback_criteria: list[str] = Field(min_length=1)
    kill_criteria: list[str] = Field(min_length=1)
    monitoring_thresholds: MonitoringThresholdsV1
    reviewer: str = Field(min_length=1)
    decision: Literal["APPROVE", "REJECT", "NEEDS MANUAL REVIEW"]
    decision_notes: str = Field(min_length=1)


class DeploymentMonitoringAppendRequest(APIModel):
    upload_token: str = Field(pattern=r"^[a-f0-9]{32}$")
    recorded_by: str = Field(min_length=1)
    notes: str = Field(min_length=1)


class AIDraftRequest(APIModel):
    campaign_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_]*$")
    selected_text: str = Field(min_length=1)
    source_title: str = Field(min_length=1)
    instrument: Literal["ES", "NQ"]


class FactoryRunNextRequest(APIModel):
    """The browser may select scope and idempotency, never a prompt or runtime."""

    campaign_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_]*$")
    request_id: str = Field(min_length=8, max_length=120)


class FactoryProposalDispositionRequest(APIModel):
    disposition: Literal["ACKNOWLEDGE", "DISMISS"]
    reviewer: str = Field(min_length=1)
    notes: str = Field(min_length=1)


class FactorySourceClaimReviewRequest(APIModel):
    claim_id: str = Field(min_length=1)
    proposed_support: Literal["DIRECT", "CONFLICTING", "INFERENCE"]
    decision: Literal["ACCEPT", "REJECT"]
    evidence_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    verification_method: str = Field(min_length=1)
    notes: str = Field(min_length=1)


class FactoryReviewedSourceRequest(APIModel):
    reviewer: str = Field(min_length=1)
    notes: str = Field(min_length=1)
    verified_metadata_fields: list[str] = Field(min_length=6, max_length=6)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    retraction_status: Literal["NOT_RETRACTED", "CORRECTED"]
    verification_method: str = Field(min_length=1)
    claim_reviews: list[FactorySourceClaimReviewRequest] = Field(min_length=1)


class FactoryReviewedHypothesisRequest(APIModel):
    reviewer: str = Field(min_length=1)
    notes: str = Field(min_length=1)
    reviewed_fields: list[str] = Field(min_length=20, max_length=20)
    objective_alignment: Literal["PASS"]
    source_claim_alignment: Literal["PASS"]
    falsifiability: Literal["PASS"]
    information_timeline_no_lookahead: Literal["PASS"]
    execution_cost_awareness: Literal["PASS"]


class FactoryReviewedEngineeringIntentRequest(APIModel):
    reviewer: str = Field(min_length=1)
    notes: str = Field(min_length=1)
    reviewed_fields: list[str] = Field(min_length=19, max_length=19)
    hypothesis_alignment: Literal["PASS"]
    unsupported_scope_confirmed: Literal["PASS"]
    causal_timeline_reviewed: Literal["PASS"]


class FactorySelectedActionRequest(APIModel):
    selected_action: Literal[
        "ABANDON_EDGE",
        "PROPOSE_SUCCESSOR",
        "START_NEW_RESEARCH_GENERATION",
        "STOP_NO_FRESH_HOLDOUT",
    ]
    reviewer: str = Field(min_length=1)
    notes: str = Field(min_length=1)


class FactorySelectedActionCompletionRequest(APIModel):
    reviewer: str = Field(min_length=1)
    notes: str = Field(min_length=1)


class APIKeyRequest(APIModel):
    api_key: str = Field(min_length=1)


class PDFExtractRequest(APIModel):
    upload_token: str = Field(pattern=r"^[a-f0-9]{32}$")
    page_indexes: list[int] = Field(min_length=1, max_length=500)


def register_api_routes(app: FastAPI, project_root: str | Path) -> None:
    """Register the versioned local JSON contract on ``app``."""

    root = Path(project_root).resolve()
    workflow = StudioWorkflowService(root)
    forward_incubation = ForwardIncubationService(root)
    campaign_cache: dict[str, tuple[float, dict[str, Any]]] = {}
    campaign_results_cache: dict[str, tuple[float, dict[str, Any]]] = {}
    campaign_attempts_cache: dict[str, tuple[float, dict[str, Any]]] = {}
    campaign_attempt_detail_cache: dict[
        tuple[str, str], tuple[float, dict[str, Any]]
    ] = {}

    def invalidate_campaign_cache(campaign_id: str) -> None:
        campaign_cache.pop(campaign_id, None)
        campaign_results_cache.pop(campaign_id, None)
        campaign_attempts_cache.pop(campaign_id, None)
        for key in [
            key for key in campaign_attempt_detail_cache if key[0] == campaign_id
        ]:
            campaign_attempt_detail_cache.pop(key, None)

    @app.exception_handler(PydanticValidationError)
    async def pydantic_error_handler(_request: Request, exc: PydanticValidationError) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(part) for part in item.get("loc", ())),
                "message": str(item.get("msg") or "Invalid value"),
            }
            for item in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "The governed contract rejected one or more fields.",
                    "occurred_at": datetime.now(timezone.utc).isoformat(),
                },
                "errors": errors,
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
        return _error_response(422, str(exc), code="validation_error")

    @app.exception_handler(FileNotFoundError)
    async def missing_handler(_request: Request, exc: FileNotFoundError) -> JSONResponse:
        return _error_response(404, str(exc), code="not_found")

    @app.exception_handler(FileExistsError)
    async def conflict_handler(_request: Request, exc: FileExistsError) -> JSONResponse:
        return _error_response(409, str(exc), code="conflict")

    @app.exception_handler(RuntimeError)
    async def runtime_handler(_request: Request, exc: RuntimeError) -> JSONResponse:
        return _error_response(409, str(exc), code="governance_blocked")

    @app.get("/api/bootstrap")
    def bootstrap() -> dict[str, Any]:
        try:
            refresh = refresh_generated_indexes_if_stale(root)
        except Exception as exc:  # fail soft for navigation; mutations still fail closed
            refresh = {"refreshed": False, "error": str(exc)}
        drafts = workflow.store.list()
        campaigns = list_published_campaigns(root)
        indexed_reviews = [
            {**item, "type": "indexed", "review_id": item.get("run_uid") or item.get("test_run_id")}
            for item in list_review_queue(root)
        ]
        mechanics_reviews = [
            {**_compact_review(item), "type": "mechanics"}
            for item in _mechanics_review_summaries(root)
        ]
        candidate_reviews = [
            {**_compact_review(item), "type": "candidate"}
            for item in _candidate_review_summaries(root)
        ]
        actionable_reviews = [
            *(item for item in mechanics_reviews if item.get("is_current_workflow")),
            *candidate_reviews,
        ]
        reviews = [*mechanics_reviews, *candidate_reviews, *indexed_reviews]
        campaigns = _campaigns_with_workflow_context(
            root,
            campaigns,
            mechanics_reviews,
        )
        jobs = _jobs(root, limit=30)
        datasets = []
        for item in list_dataset_manifests(root):
            record = _library_dataset_record(item)
            record["research_readiness"] = dataset_readiness_forecast(record)
            datasets.append(record)
        modules = _modules(root)
        settings = load_settings(project_root=root).model_dump(mode="json")
        active = sum(item.get("lifecycle") == "active" for item in campaigns)
        current_attempt_by_campaign = {
            str(item.get("campaign_id") or ""): str(item.get("attempt_id") or "")
            for item in actionable_reviews
            if item.get("is_current_workflow")
        }
        attention = []
        represented_campaigns: set[str] = set()
        for item in jobs:
            if item["operational_state"] not in {"BLOCKED", "FAILED_OPERATIONAL"}:
                continue
            campaign_id = str(item.get("campaign_id") or "")
            current_attempt_id = current_attempt_by_campaign.get(campaign_id)
            if current_attempt_id and str(item.get("attempt_id") or "") != current_attempt_id:
                continue
            if campaign_id in represented_campaigns:
                continue
            represented_campaigns.add(campaign_id)
            attention.append(item)
        attention.extend(
            item
            for item in actionable_reviews
            if item.get("type") in {"mechanics", "candidate"}
            or item.get("verdict") in {"NEEDS MANUAL REVIEW", "NEEDS_MANUAL_REVIEW"}
        )
        diagnostics = workspace_diagnostics(root, index_refresh=refresh)
        workflow_actions = global_next_actions(
            drafts=drafts,
            campaigns=campaigns,
            reviews=actionable_reviews,
            jobs=jobs,
        )
        return {
            "workspace": {
                "name": root.name,
                "path": str(root),
                "ui_runtime": "react-fastapi",
                "candidate_only": True,
                "index_refresh": refresh,
                "diagnostics": diagnostics,
                "metrics": {
                    "live_drafts": len(drafts),
                    "active_campaigns": active,
                    "review_items": len(actionable_reviews),
                    "certified_modules": len(modules),
                },
            },
            "drafts": drafts,
            "campaigns": campaigns,
            "reviews": actionable_reviews,
            "indexed_attention": indexed_reviews,
            "jobs": jobs,
            "attention": attention,
            "workflow_actions": workflow_actions,
            "libraries": {
                "datasets": datasets,
                "modules": modules,
                "prop_profiles": list_prop_profiles(),
                "account_profiles": list_account_profiles(root),
                "execution_profiles": list_execution_profiles(root),
            },
            "settings": settings,
        }

    @app.post("/api/workflow/repair-derived-views")
    def repair_derived_views() -> dict[str, Any]:
        refresh = refresh_generated_indexes_if_stale(root, force=True)
        return {
            "refresh": refresh,
            "diagnostics": workspace_diagnostics(root, index_refresh=refresh),
        }

    @app.post("/api/drafts", status_code=201)
    def create_draft(value: CreateDraftRequest) -> dict[str, Any]:
        return workflow.create_draft(**value.model_dump())

    @app.get("/api/drafts/{campaign_id}")
    def draft(campaign_id: str) -> dict[str, Any]:
        return workflow.draft_view(campaign_id)

    @app.put("/api/drafts/{campaign_id}/brief")
    def save_brief(campaign_id: str, value: BriefRequest) -> dict[str, Any]:
        return workflow.save_brief(campaign_id, value.model_dump(mode="json"))

    @app.get("/api/drafts/{campaign_id}/duplicates")
    def duplicate_context(campaign_id: str) -> dict[str, Any]:
        return workflow.duplicate_review_context(campaign_id)

    @app.put("/api/drafts/{campaign_id}/duplicates")
    def save_duplicate(campaign_id: str, value: DuplicateReviewRequest) -> dict[str, Any]:
        return workflow.save_duplicate_review(campaign_id, value.model_dump(mode="json"))

    @app.post("/api/drafts/{campaign_id}/duplicates/close")
    def close_duplicate(campaign_id: str) -> dict[str, Any]:
        return workflow.close_duplicate(campaign_id)

    @app.post("/api/drafts/{campaign_id}/dataset/select")
    def select_dataset(campaign_id: str, value: DatasetSelectRequest) -> dict[str, Any]:
        return workflow.select_dataset(campaign_id, value.dataset_id)

    @app.put("/api/drafts/{campaign_id}/execution")
    def save_execution(campaign_id: str, value: ExecutionRequest) -> dict[str, Any]:
        return workflow.save_execution(
            campaign_id,
            value.execution.model_dump(mode="json"),
            roll_policy_confirmed=value.roll_policy_confirmed,
        )

    @app.put("/api/drafts/{campaign_id}/mechanics/recipe")
    def save_recipe(campaign_id: str, value: RecipeRequest) -> dict[str, Any]:
        return workflow.save_recipe(campaign_id, value.recipe, confirmed=value.confirmed)

    @app.put("/api/drafts/{campaign_id}/mechanics/rule")
    def save_rule(campaign_id: str, value: RuleRequest) -> dict[str, Any]:
        return workflow.save_visual_rule(campaign_id, value.rule)

    @app.put("/api/drafts/{campaign_id}/mechanics/event-strategy")
    def save_event_strategy(campaign_id: str, value: EventStrategyRequest) -> dict[str, Any]:
        return workflow.save_event_strategy(campaign_id, value.strategy_id, confirmed=value.confirmed)

    @app.put("/api/drafts/{campaign_id}/mechanics/handoff")
    def save_handoff(campaign_id: str, value: HandoffRequest) -> dict[str, Any]:
        return workflow.save_engineering_handoff(campaign_id, value.model_dump(mode="json"))

    @app.get("/api/drafts/{campaign_id}/variants")
    def variants(campaign_id: str) -> dict[str, Any]:
        view = workflow.draft_view(campaign_id)
        existing = view["draft"].get("variants")
        return {
            "variants": existing or workflow.suggested_variants(campaign_id),
            "catalog": _modules(root),
            "draft_context": {
                "authoring_lane": view["draft"].get("authoring_lane"),
                "certified_recipe": view["draft"].get("certified_recipe"),
                "instrument": view["draft"].get("instrument"),
                "timeframe": view["draft"].get("timeframe"),
            },
        }

    @app.put("/api/drafts/{campaign_id}/variants")
    def save_variants(campaign_id: str, value: VariantsRequest) -> dict[str, Any]:
        return workflow.save_variants(campaign_id, value.variants)

    @app.post("/api/drafts/{campaign_id}/freeze")
    def freeze(campaign_id: str, value: ConfirmationRequest) -> dict[str, Any]:
        return workflow.freeze(campaign_id, confirmed=value.confirmed)

    @app.post("/api/drafts/{campaign_id}/publish")
    def publish(campaign_id: str) -> dict[str, Any]:
        return workflow.publish(campaign_id)

    @app.post("/api/drafts/{campaign_id}/revision", status_code=201)
    def revision(campaign_id: str, value: RevisionRequest) -> dict[str, Any]:
        return workflow.create_revision(campaign_id, revision_id=value.revision_id, reason=value.reason)

    @app.post("/api/uploads/inspect", status_code=201)
    async def inspect_upload(request: Request, filename: str) -> dict[str, Any]:
        safe_name = Path(filename).name
        if not safe_name or Path(safe_name).suffix.casefold() not in {".csv", ".parquet", ".pq"}:
            raise ValueError("upload must be a CSV or Parquet file")
        upload_root = load_storage_layout(root).studio_runtime_root / "raw-attachments"
        token = uuid4().hex
        destination = upload_root / token / safe_name
        destination.parent.mkdir(parents=True, exist_ok=False)
        size = 0
        with destination.open("wb") as handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > 4 * 1024 * 1024 * 1024:
                    raise ValueError("local import exceeds the 4 GiB Studio V1 limit")
                handle.write(chunk)
        if size == 0:
            destination.unlink(missing_ok=True)
            raise ValueError("uploaded file is empty")
        discovery = DatasetImporter(root).inspect_file(destination)
        columns = discovery["columns"]
        return {
            "upload_token": token,
            "filename": safe_name,
            "size_bytes": size,
            "columns": columns,
            "suggested_mapping": {name: _guess_column(columns, name) for name in _CANONICAL_COLUMNS},
            "discovery": discovery,
        }

    @app.get("/api/data/session-templates")
    def session_templates() -> dict[str, Any]:
        return {
            "templates": [
                {
                    "template_id": "cme_us_equity_rth",
                    "label": "CME US equity futures RTH",
                    "timezone": "America/New_York",
                    "session_start": "09:30:00",
                    "session_end": "16:00:00",
                    "symbols": ["ES", "NQ"],
                    "status": "certified_reference",
                },
                {
                    "template_id": "cme_us_equity_morning",
                    "label": "CME US equity futures morning research window",
                    "timezone": "America/New_York",
                    "session_start": "09:30:00",
                    "session_end": "11:00:00",
                    "symbols": ["ES", "NQ"],
                    "status": "certified_reference",
                },
            ],
            "note": (
                "Templates are reference controls. Dataset selection still depends on its immutable "
                "manifest, timestamp semantics, and campaign execution settings."
            ),
        }

    @app.get("/api/analysis/capabilities")
    def analysis_capabilities() -> dict[str, Any]:
        return {
            "scope": "research_and_backtesting",
            "capabilities": research_capability_matrix(),
        }

    @app.get("/api/analysis/scanner")
    def analysis_scanner() -> dict[str, Any]:
        return governed_dataset_scan(root)

    @app.get("/api/analysis/chart/{dataset_id}")
    def analysis_chart(
        dataset_id: str,
        resolution: str = "native",
        chart_type: str = "candlestick",
        limit: int = 600,
        compare_dataset_id: str | None = None,
    ) -> dict[str, Any]:
        return governed_chart_snapshot(
            root,
            dataset_id,
            resolution=resolution,
            chart_type=chart_type,
            limit=limit,
            compare_dataset_id=compare_dataset_id,
        )

    @app.get("/api/datasets/{dataset_id}")
    def dataset_detail(dataset_id: str) -> dict[str, Any]:
        return _dataset_manager_detail(root, dataset_id)

    @app.get("/api/datasets/compare/{left_id}/{right_id}")
    def compare_datasets(left_id: str, right_id: str) -> dict[str, Any]:
        left = _dataset_manager_detail(root, left_id)
        right = _dataset_manager_detail(root, right_id)
        comparable = (
            left["manifest"].get("symbol") == right["manifest"].get("symbol")
            and left["manifest"].get("timeframe") == right["manifest"].get("timeframe")
        )
        return {
            "left": left_id,
            "right": right_id,
            "comparable": comparable,
            "comparison": {
                key: {
                    "left": left["manifest"].get(key),
                    "right": right["manifest"].get(key),
                    "matches": left["manifest"].get(key) == right["manifest"].get(key),
                }
                for key in (
                    "symbol",
                    "timeframe",
                    "coverage_start",
                    "coverage_end",
                    "row_count",
                    "gap_count",
                    "quality_verdict",
                    "canonical_sha256",
                )
            },
            "warning": (
                "This is a manifest-level vendor/source comparison. It does not certify bar-for-bar "
                "equivalence or permit a failed dataset to be selected."
            ),
        }

    @app.post("/api/datasets/import", status_code=201)
    def import_dataset(value: ImportDatasetRequest) -> dict[str, Any]:
        source = _resolve_upload(root, value.upload_token)
        spec_value = value.spec.model_dump(mode="json")
        if value.roll_calendar_upload_token:
            spec_value["roll_calendar_path"] = str(_resolve_upload(root, value.roll_calendar_upload_token))
        elif value.spec.roll_policy == "explicit_roll_calendar":
            raise ValueError("explicit roll policy requires an uploaded governed roll calendar")
        result = DatasetImporter(root).import_file(source, DataImportSpec.model_validate(spec_value))
        return {
            "manifest": result.manifest.model_dump(mode="json", by_alias=True),
            "manifest_path": str(result.manifest_path),
            "canonical_path": str(result.canonical_path),
            "quarantine_path": str(result.quarantined_path),
        }

    @app.get("/api/campaigns/{campaign_id}")
    def campaign(campaign_id: str, refresh: bool = False) -> dict[str, Any]:
        cached = campaign_cache.get(campaign_id)
        if not refresh and cached and monotonic() - cached[0] < 10:
            return cached[1]
        campaigns = {str(item["campaign_id"]): item for item in list_published_campaigns(root)}
        if campaign_id not in campaigns:
            raise FileNotFoundError(f"published campaign not found: {campaign_id}")
        service = FollowUpAttemptService(root)
        partial_errors: list[dict[str, str]] = []
        attempts: list[dict[str, Any]] = []
        current_scope: dict[str, Any] = {}
        mechanics_approval: dict[str, Any] = {}
        protocol: dict[str, Any] = {}
        mechanics: dict[str, Any] = {}
        rows: list[dict[str, Any]] = []
        latest: dict[str, Any] = {}
        attempt_results: dict[str, Any] = {}
        account_evaluations: list[dict[str, Any]] = []
        if campaigns[campaign_id].get("studio_managed"):
            try:
                attempts = service.list_attempts(
                    campaign_id,
                    include_dataset_bindings=False,
                )
                current_scope = _resolve_current_work_scope(
                    root,
                    campaign_id,
                    attempts,
                )
            except Exception as exc:
                partial_errors.append({"section": "attempts", "message": str(exc)})
            try:
                mechanics_approval = _attempt_mechanics_gate(
                    root,
                    campaign_id,
                    attempts,
                    current_scope=current_scope,
                )
            except Exception as exc:
                partial_errors.append(
                    {"section": "mechanics_approval", "message": str(exc)}
                )
        try:
            protocol, mechanics = _campaign_disclosure(
                root,
                campaigns[campaign_id],
                attempts,
                mechanics_approval,
            )
        except Exception as exc:
            partial_errors.append({"section": "disclosure", "message": str(exc)})
        try:
            rows, latest = _authoritative_results(root, campaign_id)
            attempt_results = _attempt_results(root, campaign_id)
        except Exception as exc:
            partial_errors.append({"section": "results", "message": str(exc)})
        try:
            account_evaluations = _account_assessment_rows(root, campaign_id)
        except Exception as exc:
            partial_errors.append({"section": "account_evaluations", "message": str(exc)})
        workflow_context = _campaign_workflow_context(
            campaigns[campaign_id],
            attempts,
            mechanics_approval,
            attempt_results,
            current_scope=current_scope,
        )
        if mechanics:
            mechanics["default_attempt_id"] = workflow_context.get(
                "current_attempt_id"
            )
        workflow_rows = _workflow_stage_matrix(rows, workflow_context)
        research_progress = _campaign_research_progress(
            workflow_context,
            workflow_rows,
            attempt_results,
            latest,
            account_evaluations,
        )
        workflow_context["progress"] = research_progress.get("campaign") or {}
        next_variant: dict[str, Any]
        try:
            from alphaquest.studio.sequential_variants import SequentialVariantService

            next_variant = SequentialVariantService(root).eligibility(campaign_id)
        except Exception as exc:
            next_variant = {"eligible": False, "blockers": [str(exc)]}
        payload = {
            "campaign": campaigns[campaign_id],
            "attempts": attempts,
            "protocol": protocol,
            "mechanics": mechanics,
            "mechanics_approval": mechanics_approval,
            "stage_matrix": workflow_rows,
            "historical_stage_matrix": rows,
            "latest_results": latest,
            "attempt_results": attempt_results,
            "account_evaluations": account_evaluations,
            "workflow_context": workflow_context,
            "research_progress": research_progress,
            "recommended_action": workflow_context.get("primary_action", {}).get(
                "label"
            )
            or _campaign_next_action(campaigns[campaign_id], rows),
            "next_variant": next_variant,
            "partial_errors": partial_errors,
        }
        campaign_cache[campaign_id] = (monotonic(), payload)
        return payload

    @app.get("/api/campaigns/{campaign_id}/results")
    def campaign_results(campaign_id: str, refresh: bool = False) -> dict[str, Any]:
        cached = campaign_results_cache.get(campaign_id)
        if not refresh and cached and monotonic() - cached[0] < 30:
            return cached[1]
        campaigns = {
            str(item["campaign_id"]): item
            for item in list_published_campaigns(root)
        }
        if campaign_id not in campaigns:
            raise FileNotFoundError(f"published campaign not found: {campaign_id}")
        errors: list[dict[str, str]] = []
        try:
            attempt_results = _attempt_results(root, campaign_id)
        except Exception as exc:
            attempt_results = {}
            errors.append({"section": "attempt_results", "message": str(exc)})
        try:
            account_evaluations = _account_assessment_rows(root, campaign_id)
        except Exception as exc:
            account_evaluations = []
            errors.append({"section": "account_evaluations", "message": str(exc)})
        payload = {
            "campaign_id": campaign_id,
            "attempt_results": attempt_results,
            "account_evaluations": account_evaluations,
            "partial_errors": errors,
        }
        campaign_results_cache[campaign_id] = (monotonic(), payload)
        return payload

    @app.get(
        "/api/campaigns/{campaign_id}/results/{attempt_id}/{variant_id}/artifacts/{artifact_name}"
    )
    def result_artifact(
        campaign_id: str,
        attempt_id: str,
        variant_id: str,
        artifact_name: str,
    ) -> FileResponse:
        entry = _indexed_result_entry(root, campaign_id, attempt_id, variant_id)
        errors: list[str] = []
        bundle_path = _indexed_bundle_path(root, entry, errors)
        if bundle_path is None or errors:
            raise ValueError("; ".join(errors) or "finalized result bundle is unavailable")
        presentation = _present_indexed_result(
            root,
            entry,
            expected_campaign_id=campaign_id,
            expected_variant_id=variant_id,
        )
        if not presentation.get("finalization", {}).get("valid"):
            raise ValueError("result artifact download requires a complete hash-valid finalization")
        status = (presentation.get("artifact_previews") or {}).get(artifact_name)
        if not isinstance(status, Mapping) or not status.get("available") or not status.get("path"):
            raise FileNotFoundError(f"result artifact is unavailable: {artifact_name}")
        report_root = bundle_path.parent.resolve()
        path = (report_root / str(status["path"])).resolve()
        if (
            not path.is_relative_to(report_root)
            or path.suffix.casefold() != ".csv"
            or not path.is_file()
        ):
            raise ValueError("result artifact is outside its finalized report root")
        if hashlib.sha256(path.read_bytes()).hexdigest() != status.get("sha256"):
            raise ValueError("result artifact hash is stale or mismatched")
        return FileResponse(path, media_type="text/csv", filename=path.name)

    @app.get(
        "/api/campaigns/{campaign_id}/results/{attempt_id}/{variant_id}/report.zip"
    )
    def result_report_archive(
        campaign_id: str,
        attempt_id: str,
        variant_id: str,
    ) -> StreamingResponse:
        entry = _indexed_result_entry(root, campaign_id, attempt_id, variant_id)
        errors: list[str] = []
        bundle_path = _indexed_bundle_path(root, entry, errors)
        if bundle_path is None or errors:
            raise ValueError("; ".join(errors) or "finalized result bundle is unavailable")
        presentation = _present_indexed_result(
            root,
            entry,
            expected_campaign_id=campaign_id,
            expected_variant_id=variant_id,
        )
        if not presentation.get("finalization", {}).get("valid"):
            raise ValueError("report export requires a complete hash-valid finalization")
        report_root = bundle_path.parent.resolve()
        files: list[tuple[str, bytes]] = [
            (RESULT_BUNDLE_FILENAME, bundle_path.read_bytes())
        ]
        for name, status in sorted(
            (presentation.get("artifact_previews") or {}).items()
        ):
            if not isinstance(status, Mapping):
                continue
            relative = status.get("path")
            if not status.get("available") or not relative:
                continue
            path = (report_root / str(relative)).resolve()
            if (
                not path.is_relative_to(report_root)
                or path.suffix.casefold() != ".csv"
                or not path.is_file()
            ):
                raise ValueError(f"report artifact is outside its finalized report root: {name}")
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != status.get("sha256"):
                raise ValueError(f"report artifact hash is stale or mismatched: {name}")
            files.append((path.name, content))
        # Add the frozen authoring and review context without mutating or
        # re-signing any historical artifact. Finalization validity above is
        # the fail-closed gate for this derived due-diligence package.
        campaign_rows = {
            str(item.get("campaign_id")): item for item in list_published_campaigns(root)
        }
        campaign_row = campaign_rows.get(campaign_id) or {}
        campaign_path = resolve_recorded_path(
            str(campaign_row.get("path") or ""), project_root=root
        )
        campaign_root = campaign_path.parent
        try:
            source_config = _attempt_config(root, campaign_id, attempt_id, variant_id)
        except FileNotFoundError:
            source_config = campaign_root / "variants" / variant_id / "config.yaml"
        source_candidates = {
            "source/campaign.yaml": campaign_path,
            "source/strategy_spec.yaml": campaign_root / "strategy_spec.yaml",
            "source/authoring_manifest.json": campaign_root / "authoring_manifest.json",
            "source/config.yaml": source_config,
        }
        for archive_name, path in source_candidates.items():
            if path.is_file():
                files.append((archive_name, path.read_bytes()))
        for path in sorted(report_root.glob("candidate_review*.json")):
            files.append((f"reviews/{path.name}", path.read_bytes()))
        layout = load_storage_layout(root)
        approval_path = (
            layout.research_artifact_root
            / "validation_approvals"
            / campaign_id
            / (variant_id if attempt_id == "original" else attempt_id)
        )
        if attempt_id != "original":
            approval_path = approval_path / variant_id
        approval_path = approval_path / "approval.json"
        if approval_path.is_file():
            files.append(("reviews/mechanics_approval.json", approval_path.read_bytes()))
        forward_root = (
            layout.research_artifact_root
            / "forward_incubation"
            / campaign_id
            / variant_id
            / attempt_id
        )
        if forward_root.is_dir():
            for path in sorted(forward_root.rglob("*")):
                if path.is_file() and path.suffix.casefold() in {".json", ".jsonl", ".sha256", ".csv"}:
                    relative = path.relative_to(forward_root).as_posix()
                    files.append((f"forward_incubation/{relative}", path.read_bytes()))
        for name in ("finalization_manifest.json", "methodology_audit.md", "candidate_strategy_report.md"):
            path = report_root / name
            if path.is_file():
                files.append((f"reporting/{name}", path.read_bytes()))
        package_manifest = {
            "schema": "alphaquest.due-diligence-package/v1",
            "campaign_id": campaign_id,
            "attempt_id": attempt_id,
            "variant_id": variant_id,
            "scientific_effect": "NONE_DERIVED_EXPORT_ONLY",
            "files": [
                {
                    "path": filename,
                    "size_bytes": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
                for filename, content in sorted(files)
            ],
        }
        files.append(
            (
                "due_diligence_manifest.json",
                json.dumps(package_manifest, indent=2, sort_keys=True).encode("utf-8"),
            )
        )
        archive = BytesIO()
        with zipfile.ZipFile(
            archive,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as bundle_zip:
            for filename, content in sorted(files):
                info = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                bundle_zip.writestr(info, content)
        archive.seek(0)
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{campaign_id}_{variant_id}_{attempt_id}")
        return StreamingResponse(
            archive,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{safe}_due_diligence.zip"'},
        )

    @app.get("/api/campaigns/{campaign_id}/attempts")
    def campaign_attempts(campaign_id: str, refresh: bool = False) -> dict[str, Any]:
        cached = campaign_attempts_cache.get(campaign_id)
        if not refresh and cached and monotonic() - cached[0] < 30:
            return cached[1]
        campaigns = {
            str(item["campaign_id"]): item
            for item in list_published_campaigns(root)
        }
        if campaign_id not in campaigns:
            raise FileNotFoundError(f"published campaign not found: {campaign_id}")
        try:
            attempts = FollowUpAttemptService(root).list_attempts(
                campaign_id,
                include_dataset_bindings=False,
            )
            errors: list[dict[str, str]] = []
        except Exception as exc:
            attempts = []
            errors = [{"section": "attempts", "message": str(exc)}]
        payload = {
            "campaign_id": campaign_id,
            "attempts": attempts,
            "partial_errors": errors,
        }
        campaign_attempts_cache[campaign_id] = (monotonic(), payload)
        return payload

    @app.get("/api/campaigns/{campaign_id}/attempts/{attempt_id}")
    def campaign_attempt_detail(
        campaign_id: str,
        attempt_id: str,
        refresh: bool = False,
    ) -> dict[str, Any]:
        key = (campaign_id, attempt_id)
        cached = campaign_attempt_detail_cache.get(key)
        if not refresh and cached and monotonic() - cached[0] < 30:
            return cached[1]
        attempt = FollowUpAttemptService(root).attempt_detail(
            campaign_id,
            attempt_id,
        )
        payload = {
            "campaign_id": campaign_id,
            "attempt": attempt,
            "partial_errors": [],
        }
        campaign_attempt_detail_cache[key] = (monotonic(), payload)
        return payload

    @app.get("/api/campaigns/{campaign_id}/next-variant")
    def next_variant(campaign_id: str) -> dict[str, Any]:
        from alphaquest.studio.sequential_variants import SequentialVariantService

        return SequentialVariantService(root).suggestion(campaign_id)

    @app.post("/api/campaigns/{campaign_id}/next-variant", status_code=201)
    def append_next_variant(campaign_id: str, value: NextVariantRequest) -> dict[str, Any]:
        from alphaquest.studio.sequential_variants import SequentialVariantService

        result = SequentialVariantService(root).append(
            campaign_id,
            variant=value.variant,
            failure_analysis=value.failure_analysis,
            created_by=value.created_by,
        )
        invalidate_campaign_cache(campaign_id)
        return result

    @app.get("/api/campaigns/{campaign_id}/follow-up-options")
    def follow_up_options(campaign_id: str, parent_attempt_id: str = "original") -> dict[str, Any]:
        return _follow_up_options(root, campaign_id, parent_attempt_id)

    @app.post("/api/campaigns/{campaign_id}/follow-ups", status_code=201)
    def create_follow_up(campaign_id: str, value: FollowUpAttemptRequestV1) -> dict[str, Any]:
        if value.campaign_id != campaign_id:
            raise ValueError("follow-up campaign identity does not match the selected campaign")
        result = FollowUpAttemptService(root).create(value)
        invalidate_campaign_cache(campaign_id)
        return {
            "campaign_id": result.campaign_id,
            "attempt_id": result.attempt_id,
            "attempt_kind": result.attempt_kind,
            "parent_attempt_id": result.parent_attempt_id,
            "preflight_verdict": result.preflight_verdict,
            "ledger_rows_appended": result.ledger_rows_appended,
            "indexes_refreshed": result.indexes_refreshed,
            "next_action": result.next_action,
        }

    @app.post("/api/campaigns/{campaign_id}/queue-mechanics")
    def queue_mechanics(campaign_id: str, value: AttemptRequest) -> dict[str, Any]:
        jobs = FollowUpAttemptService(root).queue_mechanics_validation(campaign_id, value.attempt_id)
        invalidate_campaign_cache(campaign_id)
        return {"jobs": [_job_payload(job) for job in jobs]}

    @app.post("/api/campaigns/{campaign_id}/queue-run")
    def queue_run(campaign_id: str, value: AttemptRequest) -> dict[str, Any]:
        jobs = FollowUpAttemptService(root).queue_performance(campaign_id, value.attempt_id)
        invalidate_campaign_cache(campaign_id)
        return {"jobs": [_job_payload(job) for job in jobs]}

    @app.post(
        "/api/campaigns/{campaign_id}/attempts/{attempt_id}/recover-finalization"
    )
    def recover_attempt_finalization(campaign_id: str, attempt_id: str) -> dict[str, Any]:
        """Resume publication only; never rerun an immutable research attempt."""

        service = FollowUpAttemptService(root)
        config_path = service.target_config_path(campaign_id, attempt_id)
        cfg = _yaml_mapping(config_path)
        source_job = _finalization_recovery_job(
            root,
            campaign_id=campaign_id,
            attempt_id=attempt_id,
            variant_id=str(cfg.get("variant_id") or config_path.parent.name),
            config_path=config_path,
        )
        run_dir = resolve_recorded_path(
            str(source_job.payload.get("output_dir") or ""),
            project_root=root,
        ).resolve()
        try:
            finalizer = RunFinalizer(root)
            recovered = finalizer.recover(
                job_id=source_job.job_id,
                config_path=config_path,
                run_dir=run_dir,
            )
            experiment_recovery = _recover_experiment_finalization(
                root,
                cfg=cfg,
                result_bundle_path=recovered.result_bundle_path,
                research_verdict=recovered.research_verdict,
            )
            registry_counts = dict(finalizer.registry_refresher(root))
        except FinalizationError as exc:
            raise ValueError(str(exc)) from exc
        except ExperimentRegistryError as exc:
            raise ValueError(str(exc)) from exc
        invalidate_campaign_cache(campaign_id)
        return {
            "recovered": True,
            "source_job_id": source_job.job_id,
            "research_verdict": recovered.research_verdict,
            "finalization": recovered.as_job_result(project_root=root),
            "experiment_registry": experiment_recovery,
            "registry_counts": registry_counts,
            "next_action": "Open Results to inspect the recovered hash-valid ResultBundleV2.",
        }

    @app.post("/api/campaigns/{campaign_id}/account-assessments", status_code=201)
    def queue_account_assessment(
        campaign_id: str,
        value: AccountAssessmentRunRequest,
    ) -> dict[str, Any]:
        from alphaquest.accounts.catalog import resolve_account_profile
        config_path = _attempt_config(root, campaign_id, value.attempt_id, value.variant_id)
        entry = _indexed_result_entry(root, campaign_id, value.attempt_id, value.variant_id)
        errors: list[str] = []
        bundle_path = _indexed_bundle_path(root, entry, errors)
        if bundle_path is None:
            raise ValueError("account assessment requires a finalized ResultBundleV2: " + "; ".join(errors))
        presentation = _present_indexed_result(
            root,
            entry,
            expected_campaign_id=campaign_id,
            expected_variant_id=value.variant_id,
        )
        if (presentation.get("finalization") or {}).get("valid") is not True:
            raise ValueError("account assessment requires a complete hash-valid finalized result")
        if presentation.get("scientific_validity_verdict") != "PASS":
            raise ValueError(
                "account assessment requires scientific-validity PASS; generic objective PASS is not required"
            )

        cfg = _yaml_mapping(config_path)
        destination_contract = cfg.get("destination_benchmark_contract")
        declared_profile: Mapping[str, Any] | None = None
        if isinstance(destination_contract, Mapping):
            declared_contract_hash = str(
                cfg.get("destination_benchmark_contract_sha256") or ""
            )
            computed_contract_hash = hashlib.sha256(
                json.dumps(
                    destination_contract,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()
            if not declared_contract_hash or declared_contract_hash != computed_contract_hash:
                raise ValueError("frozen destination benchmark contract hash is missing or drifted")
            declared_profiles = destination_contract.get("profiles")
            if not isinstance(declared_profiles, list):
                raise ValueError("frozen destination benchmark contract is malformed")
            declared_profile = next(
                (
                    item
                    for item in declared_profiles
                    if isinstance(item, Mapping)
                    and item.get("profile_id") == value.profile_id
                    and item.get("profile_version") == value.profile_version
                ),
                None,
            )
            if declared_profile is None:
                raise ValueError(
                    "account assessment profile was not predeclared in the frozen destination benchmark contract"
                )

        resolved = resolve_account_profile(
            value.profile_id,
            version=value.profile_version,
            project_root=root,
        )
        if declared_profile is not None and declared_profile.get(
            "profile_sha256"
        ) != resolved.sha256:
            raise ValueError(
                "predeclared destination profile hash no longer matches the governed catalog"
            )
        acquisition = resolved.profile.rules.acquisition
        costs_required = (
            acquisition.evaluation_price_mode == "assessment_input_required"
            or acquisition.activation_fee_mode == "assessment_input_required"
        )
        evaluation_price_required = (
            acquisition.evaluation_price_mode == "assessment_input_required"
        )
        costs: dict[str, Any] | None = None
        if declared_profile is not None:
            declared_costs = declared_profile.get("costs")
            if costs_required and not isinstance(declared_costs, Mapping):
                raise ValueError(
                    "predeclared destination benchmark is missing required frozen costs"
                )
            costs = dict(declared_costs) if isinstance(declared_costs, Mapping) else None
        elif costs_required:
            missing: list[str] = []
            if evaluation_price_required and value.evaluation_purchase_price is None:
                missing.append("evaluation purchase price")
            if (
                acquisition.activation_fee_mode == "assessment_input_required"
                and value.activation_fee is None
            ):
                missing.append("activation fee")
            if value.cost_observed_at is None:
                missing.append("cost observation time")
            if not str(value.cost_source or "").strip():
                missing.append("cost source")
            if missing:
                raise ValueError("cost-adjusted account assessment requires " + ", ".join(missing))
            costs = {
                "currency": resolved.profile.identity.currency,
                "evaluation_purchase_price": value.evaluation_purchase_price or 0.0,
                "activation_fee": value.activation_fee or 0.0,
                "other_upfront_costs": value.other_upfront_costs,
                "observed_at": value.cost_observed_at.isoformat(),
                "source": str(value.cost_source).strip(),
                "include_as_replacement_cost": True,
            }
        required_attestations = set(resolved.profile.rules.manual_attestations_required)
        supplied_attestations = {
            str(item).strip() for item in value.manual_attestations if str(item).strip()
        }
        missing_attestations = sorted(required_attestations - supplied_attestations)
        if missing_attestations:
            raise ValueError(
                "confirm the required manual attestations: " + ", ".join(missing_attestations)
            )

        data_binding = cfg.get("data") if isinstance(cfg.get("data"), Mapping) else {}
        locks = {
            "result_bundle_hash": hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
            "config_hash": hashlib.sha256(config_path.read_bytes()).hexdigest(),
            "input_data_hash": str(
                data_binding.get("canonical_sha256")
                or data_binding.get("source_sha256")
                or ""
            ),
            "account_profile_hash": resolved.sha256,
        }
        if not locks["config_hash"] or not locks["input_data_hash"]:
            raise ValueError("account assessment cannot bind current config and input-data hashes")
        payload = {
            "campaign_id": campaign_id,
            "attempt_id": value.attempt_id,
            "variant_id": value.variant_id,
            "result_bundle_path": str(bundle_path),
            "config_path": str(config_path),
            "profile_id": resolved.profile.profile_id,
            "profile_version": resolved.profile.version,
            "costs": costs,
            "manual_attestations": sorted(supplied_attestations),
        }
        identity = hashlib.sha256(
            json.dumps(
                {"payload": payload, "hash_locks": locks},
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        queue = SQLiteJobQueue(load_storage_layout(root).studio_runtime_root / "jobs.sqlite3")
        job = queue.submit(
            job_type="account_assessment_run",
            campaign_id=campaign_id,
            payload=payload,
            hash_locks=locks,
            idempotency_key=f"account-assessment:{identity}",
        )
        return {"job": _job_payload(job)}

    @app.get("/api/reviews")
    def reviews() -> dict[str, Any]:
        return {
            "items": list_review_queue(root),
            "mechanics": _mechanics_review_summaries(root),
            "candidate": _candidate_review_summaries(root),
        }

    @app.post("/api/reviews/mechanics/reconciliation-upload", status_code=201)
    async def mechanics_reconciliation_upload(request: Request, filename: str) -> dict[str, Any]:
        safe_name = Path(filename).name
        if not safe_name or Path(safe_name).suffix.casefold() != ".csv":
            raise ValueError("chart reconciliation upload must be a CSV file")
        upload_root = load_storage_layout(root).studio_runtime_root / "raw-attachments"
        token = uuid4().hex
        destination = upload_root / token / safe_name
        destination.parent.mkdir(parents=True, exist_ok=False)
        size = 0
        with destination.open("wb") as handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > 10 * 1024 * 1024:
                    raise ValueError("chart reconciliation CSV exceeds the 10 MiB limit")
                handle.write(chunk)
        if size == 0:
            destination.unlink(missing_ok=True)
            raise ValueError("uploaded chart reconciliation CSV is empty")
        return {"upload_token": token, "filename": safe_name, "size_bytes": size}

    @app.post("/api/reviews/mechanics/reconcile-chart")
    def reconcile_mechanics_chart(value: MechanicsReconciliationRequest) -> dict[str, Any]:
        from alphaquest.studio.approvals import MechanicsApprovalService

        config = _attempt_config(root, value.campaign_id, value.attempt_id, value.variant_id)
        plan = MechanicsApprovalService().plan(config)
        governed: list[dict[str, Any]] = []
        for trade_id in plan.sampled_trade_ids:
            detail = _mechanics_review_detail(plan, selected_trade_id=str(trade_id))
            trade = dict(((detail.get("trade_evidence") or {}).get("trade") or {}))
            trade["trade_id"] = str(trade_id)
            governed.append(trade)
        return reconcile_chart_export(_resolve_upload(root, value.upload_token), governed)

    @app.get("/api/reviews/mechanics/{campaign_id}/{attempt_id}/{variant_id}")
    def mechanics_review(
        campaign_id: str,
        attempt_id: str,
        variant_id: str,
        trade_id: str | None = None,
    ) -> dict[str, Any]:
        from alphaquest.studio.approvals import MechanicsApprovalService

        config = _attempt_config(root, campaign_id, attempt_id, variant_id)
        plan = MechanicsApprovalService().plan(config)
        return _mechanics_review_detail(plan, selected_trade_id=trade_id)

    @app.post("/api/reviews/mechanics/annotation")
    def annotate_mechanics(value: MechanicsAnnotationRequest) -> dict[str, Any]:
        from alphaquest.dashboard.validation_app import save_manual_review_annotation
        from alphaquest.studio.approvals import MechanicsApprovalService

        config = _attempt_config(root, value.campaign_id, value.attempt_id, value.variant_id)
        service = MechanicsApprovalService()
        plan = service.plan(config)
        if not plan.evidence_dir:
            raise ValueError("mechanics evidence is unavailable")
        if str(value.trade_id) not in {str(item) for item in plan.sampled_trade_ids}:
            raise ValueError("only a trade selected by the governed sampling plan may be reviewed here")
        inspected = _mechanics_review_detail(plan, selected_trade_id=str(value.trade_id))
        if not inspected.get("trade_evidence") or inspected.get("trade_evidence_token") != value.evidence_token:
            raise ValueError("mechanics annotation requires the currently inspected hash-bound trade evidence")
        save_manual_review_annotation(
            plan.evidence_dir,
            value.trade_id,
            value.reviewer_status,
            value.reviewer_notes,
        )
        invalidate_campaign_cache(value.campaign_id)
        return _mechanics_review_detail(service.plan(config), selected_trade_id=str(value.trade_id))

    @app.post("/api/reviews/mechanics/decision")
    def decide_mechanics(value: MechanicsDecisionRequest) -> dict[str, Any]:
        from alphaquest.studio.approvals import MechanicsApprovalService

        config = _attempt_config(root, value.campaign_id, value.attempt_id, value.variant_id)
        service = MechanicsApprovalService()
        if value.decision == "approve":
            decision = service.approve(config, reviewer=value.reviewer, notes=value.notes)
        else:
            decision = service.reject(config, reviewer=value.reviewer, notes=value.notes)
        invalidate_campaign_cache(value.campaign_id)
        return {"decision": decision, "plan": _mechanics_review_detail(service.plan(config))}

    @app.post("/api/reviews/candidate/decision")
    def decide_candidate(value: CandidateDecisionRequest) -> dict[str, Any]:
        from alphaquest.dashboard.studio_app import _resolve_result_config
        from alphaquest.studio.candidate_review import CandidateReviewService

        candidate = _candidate_by_id(root, value.review_id)
        if candidate.get("evidence_token") != value.evidence_token:
            raise ValueError("candidate decision requires the currently inspected hash-bound ResultBundleV2")
        bundle_path = Path(str(candidate["path"]))
        config_path = _resolve_result_config(
            root,
            bundle_path,
            campaign_id=str(candidate["campaign_id"]),
            variant_id=str(candidate["variant_id"]),
            run_id=str(candidate["run_id"]),
        )
        review = CandidateReviewService().review(
            result_bundle_path=bundle_path,
            config_path=config_path,
            reviewer=value.reviewer,
            decision=value.decision,
            notes=value.notes,
            eligibility_basis=str(candidate.get("eligibility_basis") or "generic_scientific_pass"),  # type: ignore[arg-type]
            result_bundle_v3_path=candidate.get("result_bundle_v3_path"),
            account_assessment_id=candidate.get("account_assessment_id"),
        )
        refresh = refresh_generated_indexes_if_stale(root, force=True)
        campaigns = {
            str(item["campaign_id"]): item for item in list_published_campaigns(root)
        }
        return {
            **review.model_dump(mode="json", by_alias=True),
            "registry_refresh": refresh,
            "campaign_lifecycle": (campaigns.get(review.campaign_id) or {}).get("lifecycle"),
        }

    @app.post("/api/forward-incubations/evidence/upload", status_code=201)
    async def upload_forward_incubation_evidence(request: Request, filename: str) -> dict[str, Any]:
        safe_name = Path(filename).name
        allowed_suffixes = {
            ".csv",
            ".json",
            ".md",
            ".parquet",
            ".pdf",
            ".png",
            ".jpg",
            ".jpeg",
            ".txt",
        }
        if not safe_name or Path(safe_name).suffix.casefold() not in allowed_suffixes:
            raise ValueError("incubation evidence must be CSV, JSON, Markdown, Parquet, PDF, image, or text")
        upload_root = load_storage_layout(root).studio_runtime_root / "raw-attachments"
        token = uuid4().hex
        destination = upload_root / token / safe_name
        destination.parent.mkdir(parents=True, exist_ok=False)
        digest = hashlib.sha256()
        size = 0
        with destination.open("wb") as handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > 100 * 1024 * 1024:
                    raise ValueError("incubation evidence exceeds the 100 MiB local upload limit")
                digest.update(chunk)
                handle.write(chunk)
        if size == 0:
            destination.unlink(missing_ok=True)
            raise ValueError("incubation evidence upload is empty")
        reconciliation = (
            reconcile_forward_trade_csv(destination)
            if destination.suffix.casefold() == ".csv"
            else None
        )
        return {
            "upload_token": token,
            "filename": safe_name,
            "size_bytes": size,
            "sha256": digest.hexdigest(),
            "local_only": True,
            "durability": "copied into immutable incubation storage when appended",
            "reconciliation": reconciliation,
        }

    @app.get("/api/forward-incubations")
    def list_forward_incubations(campaign_id: str | None = None) -> dict[str, Any]:
        return {"items": forward_incubation.list(campaign_id=campaign_id)}

    @app.post("/api/forward-incubations", status_code=201)
    def start_forward_incubation(value: ForwardIncubationStartRequest) -> dict[str, Any]:
        return forward_incubation.start(**value.model_dump())

    @app.get("/api/forward-incubations/{campaign_id}/{variant_id}/{attempt_id}")
    def forward_incubation_detail(
        campaign_id: str,
        variant_id: str,
        attempt_id: str,
    ) -> dict[str, Any]:
        return forward_incubation.detail(campaign_id, variant_id, attempt_id)

    @app.post("/api/forward-incubations/{campaign_id}/{variant_id}/{attempt_id}/observations")
    def append_forward_incubation_observation(
        campaign_id: str,
        variant_id: str,
        attempt_id: str,
        value: ForwardIncubationObservationRequest,
    ) -> dict[str, Any]:
        payload = value.model_dump(exclude={"upload_token"})
        return forward_incubation.append_observation(
            campaign_id,
            variant_id,
            attempt_id,
            evidence_source_path=_resolve_upload(root, value.upload_token),
            **payload,
        )

    @app.post("/api/forward-incubations/{campaign_id}/{variant_id}/{attempt_id}/reviews")
    def append_forward_incubation_review(
        campaign_id: str,
        variant_id: str,
        attempt_id: str,
        value: ForwardIncubationReviewRequest,
    ) -> dict[str, Any]:
        payload = value.model_dump(exclude={"upload_token"})
        return forward_incubation.append_review(
            campaign_id,
            variant_id,
            attempt_id,
            evidence_source_path=_resolve_upload(root, value.upload_token),
            **payload,
        )

    @app.post("/api/forward-incubations/{campaign_id}/{variant_id}/{attempt_id}/retire")
    def retire_forward_incubation(
        campaign_id: str,
        variant_id: str,
        attempt_id: str,
        value: ForwardIncubationRetireRequest,
    ) -> dict[str, Any]:
        return forward_incubation.retire(
            campaign_id,
            variant_id,
            attempt_id,
            **value.model_dump(),
        )

    @app.get("/api/lifecycle/candidates")
    def lifecycle_candidates() -> dict[str, Any]:
        """Expose opaque identities for current, independently approved candidates."""

        return {
            "items": [
                _public_lifecycle_candidate(item)
                for item in _lifecycle_candidate_summaries(root)
            ],
            "candidate_only": True,
            "automatic_deployment_permitted": False,
        }

    @app.post("/api/portfolio-reviews", status_code=201)
    def create_portfolio_review(value: PortfolioReviewCreateRequest) -> dict[str, Any]:
        candidates = [_lifecycle_candidate_by_id(root, item) for item in value.candidate_ids]
        review, review_path = PortfolioReviewService().create(
            candidates=[
                CandidateEvidencePaths(
                    result_bundle_path=item["_result_bundle_path"],
                    candidate_review_path=item["_candidate_review_path"],
                    config_path=item["_config_path"],
                )
                for item in candidates
            ],
            output_dir=load_storage_layout(root).research_artifact_root / "portfolio_reviews",
            minimum_common_sessions=value.minimum_common_sessions,
        )
        report = PortfolioReviewService().inspect(review_path)
        return _public_portfolio_report(report, fallback_review=review)

    @app.get("/api/portfolio-reviews")
    def list_portfolio_reviews() -> dict[str, Any]:
        directory = load_storage_layout(root).research_artifact_root / "portfolio_reviews"
        items = [
            _public_portfolio_report(PortfolioReviewService().inspect(path))
            for path in sorted(directory.glob("portfolio_review_*.json"))
            if path.is_file()
        ] if directory.is_dir() else []
        return {"items": items, "automatic_deployment_permitted": False}

    @app.get("/api/portfolio-reviews/{review_id}")
    def portfolio_review_detail(review_id: str) -> dict[str, Any]:
        path = _portfolio_review_path(root, review_id)
        return _public_portfolio_report(PortfolioReviewService().inspect(path))

    @app.post("/api/deployment-decisions", status_code=201)
    def create_deployment_decision(value: DeploymentDecisionCreateRequest) -> dict[str, Any]:
        resolved = [
            (selection, _lifecycle_candidate_by_id(root, selection.candidate_id))
            for selection in value.candidates
        ]
        mismatches = [
            selection.candidate_id
            for selection, candidate in resolved
            if selection.attempt_id != candidate["attempt_id"]
        ]
        if mismatches:
            raise ValueError(
                "deployment attempt identity does not match the current candidate: "
                + ", ".join(mismatches)
            )
        portfolio_path = (
            _portfolio_review_path(root, value.portfolio_review_id)
            if value.portfolio_review_id
            else None
        )
        record, record_path = DeploymentDecisionService(root).decide(
            candidates=[
                DeploymentCandidateRequest(
                    result_bundle_path=candidate["_result_bundle_path"],
                    candidate_review_path=candidate["_candidate_review_path"],
                    config_path=candidate["_config_path"],
                    attempt_id=selection.attempt_id,
                    requested_contracts=selection.requested_contracts,
                )
                for selection, candidate in resolved
            ],
            account_limits=value.account_limits,
            rollback_criteria=value.rollback_criteria,
            kill_criteria=value.kill_criteria,
            monitoring_thresholds=value.monitoring_thresholds,
            reviewer=value.reviewer,
            decision=value.decision,
            decision_notes=value.decision_notes,
            output_dir=load_storage_layout(root).research_artifact_root / "deployment_decisions",
            portfolio_review_path=portfolio_path,
        )
        report = DeploymentDecisionService(root).inspect(record_path)
        return _public_deployment_report(report, fallback_decision=record)

    @app.get("/api/deployment-decisions")
    def list_deployment_decisions() -> dict[str, Any]:
        directory = load_storage_layout(root).research_artifact_root / "deployment_decisions"
        items = [
            _public_deployment_report(DeploymentDecisionService(root).inspect(path))
            for path in sorted(directory.glob("deployment_decision_*.json"))
            if path.is_file()
        ] if directory.is_dir() else []
        return {
            "items": items,
            "order_submission_permitted": False,
            "automatic_retirement_permitted": False,
        }

    @app.get("/api/deployment-decisions/{decision_id}")
    def deployment_decision_detail(decision_id: str) -> dict[str, Any]:
        path = _deployment_decision_path(root, decision_id)
        return _public_deployment_report(DeploymentDecisionService(root).inspect(path))

    @app.post("/api/deployment-monitoring/evidence/upload", status_code=201)
    async def upload_deployment_monitoring_evidence(
        request: Request,
        filename: str,
    ) -> dict[str, Any]:
        safe_name = Path(filename).name
        if not safe_name or Path(safe_name).suffix.casefold() != ".csv":
            raise ValueError("deployment monitoring evidence must be a CSV file")
        upload_root = load_storage_layout(root).studio_runtime_root / "raw-attachments"
        token = uuid4().hex
        destination = upload_root / token / safe_name
        destination.parent.mkdir(parents=True, exist_ok=False)
        digest = hashlib.sha256()
        size = 0
        with destination.open("wb") as handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > 100 * 1024 * 1024:
                    raise ValueError("deployment monitoring evidence exceeds the 100 MiB local limit")
                digest.update(chunk)
                handle.write(chunk)
        if size == 0:
            destination.unlink(missing_ok=True)
            raise ValueError("deployment monitoring evidence upload is empty")
        return {
            "upload_token": token,
            "filename": safe_name,
            "size_bytes": size,
            "sha256": digest.hexdigest(),
            "local_only": True,
            "durability": "copied into immutable monitoring storage when appended",
        }

    @app.post("/api/deployment-decisions/{decision_id}/monitoring", status_code=201)
    def append_deployment_monitoring(
        decision_id: str,
        value: DeploymentMonitoringAppendRequest,
    ) -> dict[str, Any]:
        decision_path = _deployment_decision_path(root, decision_id)
        detail = DeploymentMonitoringService(
            project_root=root,
            deployment_decision_path=decision_path,
            output_root=load_storage_layout(root).research_artifact_root / "deployment_monitoring",
        ).append(
            source_trade_log_path=_resolve_upload(root, value.upload_token),
            recorded_by=value.recorded_by,
            notes=value.notes,
        )
        return _public_monitoring_detail(detail)

    @app.get("/api/deployment-decisions/{decision_id}/monitoring")
    def deployment_monitoring_detail(decision_id: str) -> dict[str, Any]:
        decision_path = _deployment_decision_path(root, decision_id)
        detail = DeploymentMonitoringService(
            project_root=root,
            deployment_decision_path=decision_path,
            output_root=load_storage_layout(root).research_artifact_root / "deployment_monitoring",
        ).detail()
        return _public_monitoring_detail(detail)

    @app.get("/api/libraries")
    def libraries() -> dict[str, Any]:
        datasets = [
            _library_dataset_record(item) for item in list_dataset_manifests(root)
        ]
        usage = _dataset_usage(root)
        for dataset in datasets:
            dataset["used_by"] = usage.get(str(dataset.get("dataset_id") or ""), [])
            dataset["research_readiness"] = dataset_readiness_forecast(dataset)
        modules = _modules(root)
        module_usage = _module_usage(root)
        for module in modules:
            module["used_by"] = module_usage.get(str(module.get("name") or ""), [])
        return {
            "datasets": datasets,
            "modules": modules,
            "prop_profiles": list_prop_profiles(),
            "account_profiles": list_account_profiles(root),
            "execution_profiles": list_execution_profiles(root),
        }

    @app.post("/api/strategies/{strategy_id}/certify", status_code=201)
    def queue_strategy_certification(
        strategy_id: str,
        value: StrategyCertificationRunRequest,
    ) -> dict[str, Any]:
        from alphaquest.strategy_certification import (
            StrategyPackageAccess,
            compute_implementation_sha256,
            get_strategy_certification,
            load_strategy_package_availability,
        )

        policy = load_strategy_package_availability(root)
        engineering_allowed = (
            policy.allows(strategy_id, StrategyPackageAccess.ENGINEERING)
            if hasattr(policy, "allows")
            else strategy_id in policy.active_strategy_ids
        )
        if not engineering_allowed:
            raise ValueError(
                "only a development, active, or deprecated strategy package may be recertified from Studio"
            )
        certification = get_strategy_certification(
            strategy_id,
            root,
            require_current=False,
            access=StrategyPackageAccess.ENGINEERING,
        )
        actual_hash = compute_implementation_sha256(root, certification.source_files)
        manifest_hash = hashlib.sha256(certification.manifest_path.read_bytes()).hexdigest()
        queue = SQLiteJobQueue(load_storage_layout(root).studio_runtime_root / "jobs.sqlite3")
        job = queue.submit(
            job_type="strategy_certification_run",
            payload={
                "strategy_id": strategy_id,
                "request_id": value.request_id,
                "required_tests": list(certification.required_tests),
            },
            hash_locks={
                "implementation_hash": actual_hash,
                "certification_manifest_hash": manifest_hash,
            },
            idempotency_key=(
                f"strategy-certification:{strategy_id}:{actual_hash}:{value.request_id}"
            ),
        )
        return {"job": _job_payload(job)}

    @app.get("/api/jobs")
    def jobs(limit: int = 100) -> dict[str, Any]:
        return {"jobs": _jobs(root, limit=max(1, min(500, limit)))}

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict[str, Any]:
        database = load_storage_layout(root).studio_runtime_root / "jobs.sqlite3"
        if not database.is_file():
            raise FileNotFoundError("Studio job queue does not exist")
        return _job_payload(SQLiteJobQueue(database).request_cancel(job_id))

    @app.get("/api/factory/status")
    def factory_status(campaign_id: str | None = None) -> dict[str, Any]:
        from alphaquest.studio.factory_service import ResearchFactoryService

        return ResearchFactoryService(root).status(campaign_id=campaign_id)

    @app.get("/api/factory/tasks")
    def factory_tasks(limit: int = 100) -> dict[str, Any]:
        from alphaquest.studio.factory_service import ResearchFactoryService

        return {
            "tasks": ResearchFactoryService(root).list_tasks(
                limit=max(1, min(500, limit))
            )
        }

    @app.get("/api/factory/tasks/{task_id}")
    def factory_task(task_id: str) -> dict[str, Any]:
        from alphaquest.studio.factory_service import ResearchFactoryService

        try:
            task = ResearchFactoryService(root).get_task(task_id)
        except KeyError as exc:
            raise FileNotFoundError(f"Codex factory task does not exist: {task_id}") from exc
        return {"task": task}

    @app.post("/api/factory/run-next", status_code=202)
    def factory_run_next(value: FactoryRunNextRequest) -> dict[str, Any]:
        from alphaquest.studio.factory_service import ResearchFactoryService

        task = ResearchFactoryService(root).enqueue_next(
            campaign_id=value.campaign_id,
            request_id=value.request_id,
        )
        return {
            "task": task,
            "queued_only": True,
            "codex_invoked_inline": False,
            "proposal_applied": False,
        }

    @app.post("/api/factory/tasks/{task_id}/cancel")
    def factory_cancel_task(task_id: str) -> dict[str, Any]:
        from alphaquest.studio.factory_service import ResearchFactoryService

        try:
            task = ResearchFactoryService(root).cancel(task_id)
        except KeyError as exc:
            raise FileNotFoundError(f"Codex factory task does not exist: {task_id}") from exc
        return {"task": task}

    @app.post("/api/factory/tasks/{task_id}/proposal-disposition")
    def factory_proposal_disposition(
        task_id: str,
        value: FactoryProposalDispositionRequest,
    ) -> dict[str, Any]:
        from alphaquest.studio.factory_service import ResearchFactoryService

        try:
            task = ResearchFactoryService(root).record_proposal_disposition(
                task_id,
                disposition=value.disposition,
                reviewer=value.reviewer,
                notes=value.notes,
            )
        except KeyError as exc:
            raise FileNotFoundError(f"Codex factory task does not exist: {task_id}") from exc
        return {"task": task}

    @app.post("/api/factory/tasks/{task_id}/reviewed-source-evidence")
    def factory_reviewed_source_evidence(
        task_id: str,
        value: FactoryReviewedSourceRequest,
    ) -> dict[str, Any]:
        from alphaquest.studio.factory_reviews import SourceEvidenceHumanVerificationV1
        from alphaquest.studio.factory_service import ResearchFactoryService

        verification = SourceEvidenceHumanVerificationV1(
            review_id=f"source_review_{uuid4().hex}",
            reviewer=value.reviewer,
            reviewed_at=datetime.now(timezone.utc),
            verified_metadata_fields=value.verified_metadata_fields,
            content_sha256=value.content_sha256,
            retraction_status=value.retraction_status,
            verification_method=value.verification_method,
            claim_reviews=[item.model_dump() for item in value.claim_reviews],
            notes=value.notes,
        )
        try:
            artifact = ResearchFactoryService(root).record_reviewed_source_evidence(
                task_id,
                verification=verification,
            )
        except KeyError as exc:
            raise FileNotFoundError(f"Codex factory task does not exist: {task_id}") from exc
        return {
            "reviewed_artifact": artifact,
            "campaign_mutated": False,
            "mechanics_approved": False,
            "testing_authorized": False,
        }

    @app.post("/api/factory/tasks/{task_id}/reviewed-hypothesis")
    def factory_reviewed_hypothesis(
        task_id: str,
        value: FactoryReviewedHypothesisRequest,
    ) -> dict[str, Any]:
        from alphaquest.studio.factory_reviews import HypothesisHumanAcceptanceV1
        from alphaquest.studio.factory_service import ResearchFactoryService

        acceptance = HypothesisHumanAcceptanceV1(
            review_id=f"hypothesis_review_{uuid4().hex}",
            reviewer=value.reviewer,
            reviewed_at=datetime.now(timezone.utc),
            reviewed_fields=value.reviewed_fields,
            objective_alignment=value.objective_alignment,
            source_claim_alignment=value.source_claim_alignment,
            falsifiability=value.falsifiability,
            information_timeline_no_lookahead=value.information_timeline_no_lookahead,
            execution_cost_awareness=value.execution_cost_awareness,
            notes=value.notes,
        )
        try:
            artifact = ResearchFactoryService(root).record_reviewed_hypothesis(
                task_id,
                acceptance=acceptance,
            )
        except KeyError as exc:
            raise FileNotFoundError(f"Codex factory task does not exist: {task_id}") from exc
        return {
            "reviewed_artifact": artifact,
            "campaign_mutated": False,
            "mechanics_approved": False,
            "testing_authorized": False,
        }

    @app.post("/api/factory/tasks/{task_id}/reviewed-engineering-intent")
    def factory_reviewed_engineering_intent(
        task_id: str,
        value: FactoryReviewedEngineeringIntentRequest,
    ) -> dict[str, Any]:
        from alphaquest.studio.factory_reviews import (
            EngineeringHandoffIntentHumanAcceptanceV1,
        )
        from alphaquest.studio.factory_service import ResearchFactoryService

        acceptance = EngineeringHandoffIntentHumanAcceptanceV1(
            review_id=f"engineering_intent_review_{uuid4().hex}",
            reviewer=value.reviewer,
            reviewed_at=datetime.now(timezone.utc),
            reviewed_fields=value.reviewed_fields,
            hypothesis_alignment=value.hypothesis_alignment,
            unsupported_scope_confirmed=value.unsupported_scope_confirmed,
            causal_timeline_reviewed=value.causal_timeline_reviewed,
            notes=value.notes,
        )
        try:
            artifact = ResearchFactoryService(root).record_reviewed_engineering_handoff_intent(
                task_id,
                acceptance=acceptance,
            )
        except KeyError as exc:
            raise FileNotFoundError(f"Codex factory task does not exist: {task_id}") from exc
        return {
            "reviewed_artifact": artifact,
            "campaign_mutated": False,
            "mechanics_approved": False,
            "testing_authorized": False,
        }

    @app.post("/api/factory/tasks/{task_id}/selected-action")
    def factory_selected_action(
        task_id: str,
        value: FactorySelectedActionRequest,
    ) -> dict[str, Any]:
        from alphaquest.studio.factory_service import ResearchFactoryService

        try:
            task = ResearchFactoryService(root).record_selected_next_action(
                task_id,
                selected_action=value.selected_action,
                reviewer=value.reviewer,
                notes=value.notes,
            )
        except KeyError as exc:
            raise FileNotFoundError(f"Codex factory task does not exist: {task_id}") from exc
        return {"task": task}

    @app.post("/api/factory/tasks/{task_id}/selected-action-completion")
    def factory_selected_action_completion(
        task_id: str,
        value: FactorySelectedActionCompletionRequest,
    ) -> dict[str, Any]:
        from alphaquest.studio.factory_service import ResearchFactoryService

        try:
            task = ResearchFactoryService(root).record_selected_action_completion(
                task_id,
                reviewer=value.reviewer,
                notes=value.notes,
            )
        except KeyError as exc:
            raise FileNotFoundError(f"Codex factory task does not exist: {task_id}") from exc
        return {"task": task}

    @app.post("/api/factory/pause")
    def factory_pause() -> dict[str, Any]:
        from alphaquest.studio.factory_service import ResearchFactoryService

        return ResearchFactoryService(root).pause()

    @app.post("/api/factory/resume")
    def factory_resume() -> dict[str, Any]:
        from alphaquest.studio.factory_service import ResearchFactoryService

        return ResearchFactoryService(root).resume()

    @app.post("/api/tutorial/run")
    def run_tutorial(value: TutorialRequest) -> dict[str, Any]:
        from alphaquest.tutorial import run_tutorial

        output = root / "examples" / "tutorial_campaign" / "generated"
        result = run_tutorial(output_root=output, execute=True)
        return {**result, "reset_requested": value.reset}

    @app.get("/api/settings")
    def settings() -> dict[str, Any]:
        return load_settings(project_root=root).model_dump(mode="json")

    @app.put("/api/settings")
    def update_settings(value: StudioSettings) -> dict[str, Any]:
        path = save_settings(value, project_root=root)
        return {"settings": value.model_dump(mode="json"), "saved": True, "path": str(path)}

    @app.get("/api/ai/status")
    def ai_status() -> dict[str, Any]:
        from alphaquest.studio.ai import load_api_key

        current = load_settings(project_root=root)
        return {
            "configured": bool(load_api_key()),
            "model": current.openai_model,
            "retention_notice": current.openai_retention_notice,
            "zero_data_retention_enabled": current.openai_zero_data_retention_enabled,
            "privacy_boundary": "selected research prose only; no market data, results, files, web tools, or execution",
        }

    @app.post("/api/ai/pdf/inspect", status_code=201)
    async def inspect_research_pdf(request: Request, filename: str) -> dict[str, Any]:
        from pypdf import PdfReader

        safe_name = Path(filename).name
        if not safe_name or Path(safe_name).suffix.casefold() != ".pdf":
            raise ValueError("research attachment must be a PDF")
        upload_root = load_storage_layout(root).studio_runtime_root / "raw-attachments"
        token = uuid4().hex
        destination = upload_root / token / safe_name
        destination.parent.mkdir(parents=True, exist_ok=False)
        size = 0
        with destination.open("wb") as handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > 50 * 1024 * 1024:
                    raise ValueError("research PDF exceeds the 50 MiB local extraction limit")
                handle.write(chunk)
        if size == 0:
            destination.unlink(missing_ok=True)
            raise ValueError("research PDF is empty")
        try:
            reader = PdfReader(str(destination))
            pages = []
            for index, page in enumerate(reader.pages):
                extracted = page.extract_text() or ""
                pages.append(
                    {
                        "index": index,
                        "page_number": index + 1,
                        "characters": len(extracted),
                        "preview": " ".join(extracted.split())[:240],
                    }
                )
        except Exception as exc:
            raise ValueError(f"research PDF could not be parsed locally: {exc}") from exc
        return {
            "upload_token": token,
            "filename": safe_name,
            "size_bytes": size,
            "pages": pages,
            "local_only": True,
        }

    @app.post("/api/ai/pdf/extract")
    def extract_research_pdf(value: PDFExtractRequest) -> dict[str, Any]:
        from alphaquest.studio.ai import extract_pdf_text

        path = _resolve_upload(root, value.upload_token)
        if path.suffix.casefold() != ".pdf":
            raise ValueError("upload token does not identify a research PDF")
        text_value = extract_pdf_text(path, page_indexes=value.page_indexes)
        if not text_value:
            raise ValueError("selected PDF pages contain no extractable text")
        return {
            "selected_text": text_value,
            "characters": len(text_value),
            "page_indexes": value.page_indexes,
            "local_only": True,
        }

    @app.put("/api/ai/key")
    def store_ai_key(value: APIKeyRequest) -> dict[str, Any]:
        from alphaquest.studio.ai import save_api_key

        if load_settings(project_root=root).assistant_mode != "legacy_openai_api":
            raise ValueError(
                "OpenAI API key storage requires explicit legacy_openai_api assistant mode"
            )
        save_api_key(value.api_key)
        return {"configured": True, "stored_in": "operating-system keychain"}

    @app.delete("/api/ai/key")
    def remove_ai_key() -> dict[str, Any]:
        from alphaquest.studio.ai import delete_api_key

        delete_api_key()
        return {"configured": False}

    @app.post("/api/ai/suggest")
    def ai_suggest(value: AIDraftRequest) -> dict[str, Any]:
        from alphaquest.studio.ai import OpenAIResearchDraftAdapter

        if load_settings(project_root=root).assistant_mode != "legacy_openai_api":
            raise ValueError(
                "metered OpenAI API drafting requires explicit legacy_openai_api assistant mode"
            )
        draft_document = workflow.store.load(value.campaign_id)
        if (draft_document.get("draft") or {}).get("frozen"):
            raise ValueError("AI drafting is unavailable after the research protocol is frozen")
        settings_value = load_settings(project_root=root)
        if not settings_value.openai_model.strip():
            raise ValueError("an administrator must configure a pinned OpenAI model ID first")
        suggestion, provenance = OpenAIResearchDraftAdapter(model=settings_value.openai_model).suggest(
            value.selected_text,
            source_title=value.source_title,
            instrument=value.instrument,
        )
        state = workflow.store.load_state(value.campaign_id)
        events = list(state.get("ai_provenance_events") or [])
        events.append(provenance.model_dump(mode="json", by_alias=True))
        workflow.store.save_state(
            value.campaign_id,
            {**state, "ai_provenance_events": events},
        )
        return {
            "suggestion": suggestion.model_dump(mode="json"),
            "provenance": provenance.model_dump(mode="json", by_alias=True),
            "requires_human_confirmation": True,
        }


def _error_response(status_code: int, message: str, *, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )


def _modules(project_root: str | Path | None = None) -> list[dict[str, Any]]:
    from alphaquest.strategy_certification import (
        StrategyCertificationError,
        audit_strategy_certification,
        load_strategy_certifications,
        load_strategy_package_availability,
    )

    try:
        certifications = load_strategy_certifications(
            project_root,
            require_current=False,
        )
    except StrategyCertificationError:
        # Navigation remains available in minimal workspaces, but no strategy
        # package is exposed when repository-owned availability cannot be proven.
        certifications = {}
    try:
        package_policy = load_strategy_package_availability(project_root)
    except StrategyCertificationError:
        package_policy = None
    result = []
    for item in get_certified_module_catalog().all():
        record = item.model_dump(mode="json", by_alias=True)
        certification = certifications.get(item.name) if item.module_type == "entry" else None
        if certification is not None:
            try:
                certification_errors = [
                    str(error)
                    for error in audit_strategy_certification(
                        certification,
                        project_root,
                    )
                ]
            except Exception as exc:  # fail closed without taking the library offline
                certification_errors = [f"certification audit could not be completed: {exc}"]
            certification_current = not certification_errors
            record.update(
                {
                    "certification_status": certification.certification_status,
                    "certification_current": certification_current,
                    "certification_errors": certification_errors,
                    "available_for_publication": (
                        certification.studio.get("visible") is True
                        and certification_current
                    ),
                    "strategy_label": certification.studio.get("label"),
                    "strategy_description": certification.studio.get("description"),
                    "implementation_version": certification.implementation_version,
                    "implementation_sha256": certification.implementation_sha256,
                    "certification_manifest_sha256": certification.manifest_sha256,
                    "required_test_categories": list(certification.required_test_categories),
                    "required_tests": list(certification.required_tests),
                    "strategy_parameters": {
                        name: parameter.public_record()
                        for name, parameter in certification.parameters.items()
                    },
                    "strategy_package": True,
                    "strategy_package_lifecycle": (
                        package_policy.lifecycle_for(certification.strategy_id).value
                        if package_policy is not None
                        and hasattr(package_policy, "lifecycle_for")
                        else "active"
                        if package_policy is not None
                        and certification.strategy_id in package_policy.active_strategy_ids
                        else "unavailable"
                    ),
                    "active_strategy_package": (
                        certification.strategy_id in package_policy.active_strategy_ids
                        if package_policy is not None
                        else False
                    ),
                }
            )
        result.append(record)
    return result


def _library_dataset_record(value: Mapping[str, Any]) -> dict[str, Any]:
    """Add human-facing provenance without mutating the governed manifest schema."""

    record = dict(value)
    dataset_id = str(record.get("dataset_id") or "")
    event_source = (
        record.get("event_source")
        if isinstance(record.get("event_source"), Mapping)
        else {}
    )
    source_type = str(event_source.get("source") or "").strip()
    if not source_type:
        lowered = dataset_id.lower()
        if "sierra" in lowered:
            source_type = "sierra_scid_bars"
        elif "databento" in lowered:
            source_type = "databento"
        else:
            source_type = "not_recorded"
    lowered = dataset_id.lower()
    display_name = dataset_id
    if "databento_trade_events" in lowered:
        display_name = f"{record.get('symbol') or 'Futures'} Databento trade events"
    elif "sierra_price_only" in lowered:
        display_name = f"{record.get('symbol') or 'Futures'} Sierra price-only TPO bars"
    elif "sierra_yush_events" in lowered:
        display_name = f"{record.get('symbol') or 'Futures'} Sierra order-flow events"
        if lowered.endswith("_inv02"):
            display_name += " · inversion-tolerant revision"
    capabilities = list(record.get("certified_features") or [])
    required_capability = event_source.get("required_capability")
    if required_capability and required_capability not in capabilities:
        capabilities.append(required_capability)
    if event_source:
        capabilities.extend(
            item
            for item in ("ordered_trade_events", "intrabar_execution")
            if item not in capabilities
        )
    record.update(
        {
            "display_name": display_name,
            "source_type": source_type,
            "storage_format": record.get("source"),
            "capabilities": capabilities,
        }
    )
    return record


def _dataset_usage(root: Path) -> dict[str, list[dict[str, str]]]:
    """Return concise governed campaign/variant references for library cards."""

    usage: dict[str, list[dict[str, str]]] = {}
    for campaign in list_published_campaigns(root):
        campaign_id = str(campaign.get("campaign_id") or "")
        campaign_title = str(campaign.get("title") or campaign_id)
        source_path = root / str(campaign.get("path") or "")
        if not source_path.is_file():
            continue
        for config_path in sorted(source_path.parent.glob("variants/*/config.yaml")):
            try:
                config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                continue
            data = config.get("data") if isinstance(config.get("data"), Mapping) else {}
            dataset_id = str(data.get("dataset_id") or "").strip()
            if not dataset_id:
                continue
            reference = {
                "campaign_id": campaign_id,
                "campaign_title": campaign_title,
                "variant_id": config_path.parent.name,
            }
            if reference not in usage.setdefault(dataset_id, []):
                usage[dataset_id].append(reference)
    return usage


def _module_usage(root: Path) -> dict[str, list[dict[str, str]]]:
    """Return campaign/variant references for certified strategy packages."""

    usage: dict[str, list[dict[str, str]]] = {}
    for campaign in list_published_campaigns(root):
        campaign_id = str(campaign.get("campaign_id") or "")
        campaign_title = str(campaign.get("title") or campaign_id)
        source_path = root / str(campaign.get("path") or "")
        if not source_path.is_file():
            continue
        for config_path in sorted(source_path.parent.glob("variants/*/config.yaml")):
            try:
                config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                continue
            certification = (
                config.get("strategy_certification")
                if isinstance(config.get("strategy_certification"), Mapping)
                else {}
            )
            strategy = (
                config.get("strategy")
                if isinstance(config.get("strategy"), Mapping)
                else {}
            )
            entry = (
                strategy.get("entry")
                if isinstance(strategy.get("entry"), Mapping)
                else {}
            )
            names = {
                str(certification.get("strategy_id") or "").strip(),
                str(entry.get("name") or "").strip(),
            }
            reference = {
                "campaign_id": campaign_id,
                "campaign_title": campaign_title,
                "variant_id": config_path.parent.name,
            }
            for name in names - {""}:
                if reference not in usage.setdefault(name, []):
                    usage[name].append(reference)
    return usage


def _compact_review(value: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "review_id",
        "campaign_id",
        "campaign_title",
        "variant_id",
        "attempt_id",
        "run_id",
        "status",
        "verdict",
        "ready_for_approval",
        "review_status",
        "blockers",
        "review_blockers",
        "sample_progress",
        "sampled_trade_ids",
        "unreviewed_trade_ids",
        "non_correct_trade_ids",
        "attempt_kind",
        "attempt_label",
        "created_at",
        "is_current_workflow",
        "queue_scope",
    }
    return {key: item for key, item in value.items() if key in allowed}


def _jobs(root: Path, *, limit: int) -> list[dict[str, Any]]:
    database = load_storage_layout(root).studio_runtime_root / "jobs.sqlite3"
    if not database.is_file():
        return []
    return [_job_payload(job) for job in SQLiteJobQueue(database).list_jobs(limit=limit)]


def _job_payload(job: Any) -> dict[str, Any]:
    progress = _job_progress_payload(job)
    return {
        "job_id": job.job_id,
        "job_type": job.job_type,
        "campaign_id": job.campaign_id,
        "variant_id": job.payload.get("variant_id"),
        "attempt_id": job.payload.get("attempt_id"),
        "operational_state": job.state.value,
        "research_verdict": job.research_verdict,
        "attempt_reserved": job.attempt_reserved,
        "blocked_reason": job.blocked_reason,
        "error": job.error,
        "result": job.result,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "heartbeat_at": job.heartbeat_at.isoformat() if job.heartbeat_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "progress": progress["percent"] if progress else None,
        "progress_detail": progress,
        "cancellable": job.state
        in {OperationalState.QUEUED, OperationalState.RUNNING, OperationalState.CANCEL_REQUESTED},
    }


def _job_progress_payload(job: Any) -> dict[str, Any] | None:
    progress = job.progress
    if progress is None:
        return None
    end = job.finished_at or datetime.now(timezone.utc)
    elapsed_seconds = max(0.0, (end - job.started_at).total_seconds()) if job.started_at else None
    phase_elapsed = max(0.0, (end - progress.phase_started_at).total_seconds())
    work_started_at = progress.work_started_at or progress.phase_started_at
    work_elapsed = max(0.0, (end - work_started_at).total_seconds())
    eta_seconds = None
    if (
        job.state in {OperationalState.RUNNING, OperationalState.CANCEL_REQUESTED}
        and progress.phase == "event_replay"
        and 15.0 < progress.percent < 85.0
    ):
        phase_fraction = (progress.percent - 15.0) / 70.0
        eta_seconds = phase_elapsed / phase_fraction * (1.0 - phase_fraction)
    elif (
        job.state in {OperationalState.RUNNING, OperationalState.CANCEL_REQUESTED}
        and progress.completed is not None
        and progress.total is not None
        and 0 < progress.completed < progress.total
    ):
        eta_seconds = work_elapsed / progress.completed * (progress.total - progress.completed)
    throughput_per_hour = None
    if progress.completed is not None and progress.completed > 0 and work_elapsed > 0:
        throughput_per_hour = progress.completed / work_elapsed * 3600.0
    estimated_finish_at = (
        (end + timedelta(seconds=eta_seconds)).isoformat()
        if eta_seconds is not None
        else None
    )
    parallelism_warning = None
    if (
        progress.active_workers is not None
        and progress.expected_workers is not None
        and progress.active_workers < progress.expected_workers
    ):
        parallelism_warning = (
            f"Only {progress.active_workers} of {progress.expected_workers} expected workers are active"
        )
    return {
        **progress.model_dump(mode="json", by_alias=True),
        "elapsed_seconds": elapsed_seconds,
        "work_elapsed_seconds": work_elapsed,
        "eta_seconds": eta_seconds,
        "throughput_per_hour": throughput_per_hour,
        "estimated_finish_at": estimated_finish_at,
        "parallelism_warning": parallelism_warning,
    }


def _authoritative_results(root: Path, campaign_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Present only complete, hash-valid ResultBundleV2 transactions.

    The source results index is a routing and lineage surface.  Its verdicts
    and metrics are never presentation-authoritative: every terminal result is
    reloaded from the immutable bundle and its adjacent finalization contract.
    """

    rows, indexed = _results_matrix(root, campaign_id)
    presented: dict[str, dict[str, Any]] = {}
    row_by_variant = {str(item.get("variant") or ""): item for item in rows}
    archived = _archived_run_keys(root, campaign_id)
    for variant_id, entry in indexed.items():
        run_id = str(entry.get("test_run_id") or entry.get("run_id") or "")
        if (str(variant_id), run_id) in archived:
            row = row_by_variant.get(str(variant_id))
            if row is not None:
                row.update(
                    {
                        "research verdict": "NEEDS MANUAL REVIEW",
                        "first failed or unresolved gate": "historical_unreviewed_verdict_archived",
                        "run": run_id or None,
                    }
                )
            continue
        payload = _present_indexed_result(
            root,
            entry,
            expected_campaign_id=campaign_id,
            expected_variant_id=str(variant_id),
        )
        payload["attempt_id"] = entry.get("attempt_id")
        payload["attempt_kind"] = entry.get("attempt_kind")
        presented[str(variant_id)] = payload
        row = row_by_variant.get(str(variant_id))
        if row is None:
            continue
        row.update(
            {
                "research verdict": payload["research_verdict"],
                # A complete hash-valid finalization transaction is the
                # authoritative current operational outcome. The original
                # failed publication job remains visible in Jobs history.
                "operational state": "SUCCEEDED",
                "first failed or unresolved gate": payload["first_failed_or_unresolved_gate"],
                "run": payload.get("run_id"),
                "diagnostic only": bool(entry.get("diagnostic_only")),
            }
        )

    # A terminal worker/index verdict without a valid finalized bundle is not
    # scientific evidence.  Preserve in-flight PENDING rows, but fail closed
    # for every terminal state that lacks an authoritative presentation.
    for row in rows:
        variant_id = str(row.get("variant") or "")
        if variant_id in presented:
            continue
        if row.get("first failed or unresolved gate") == "historical_unreviewed_verdict_archived":
            continue
        verdict = str(row.get("research verdict") or "PENDING")
        operational = str(row.get("operational state") or "NOT_QUEUED")
        if verdict in {"PASS", "FAIL", "NEEDS MANUAL REVIEW"} or operational in {
            "SUCCEEDED",
            "FAILED_OPERATIONAL",
            "CANCELLED",
        }:
            row.update(
                {
                    "research verdict": "NEEDS MANUAL REVIEW",
                    "first failed or unresolved gate": "result_bundle_v2_finalization",
                }
            )
    return rows, presented


def _attempt_results(root: Path, campaign_id: str) -> dict[str, dict[str, dict[str, Any]]]:
    """Return finalized results keyed by the exact immutable attempt and variant.

    ``results_index.yaml`` is lineage/navigation metadata only. Every exposed
    result is still reloaded through the hash-valid ResultBundleV2 presenter.
    Incomplete attempts remain visible to History, but never masquerade as a
    governed result.
    """

    index_path = (
        load_storage_layout(root).active_campaign_root
        / campaign_id
        / "results_index.yaml"
    )
    source = _yaml_mapping(index_path)
    runs = source.get("runs") if isinstance(source.get("runs"), list) else []
    archived = _archived_run_keys(root, campaign_id)
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for entry in runs:
        if not isinstance(entry, Mapping):
            continue
        attempt_id = str(entry.get("attempt_id") or "")
        variant_id = str(entry.get("variant_id") or "")
        run_id = str(entry.get("test_run_id") or entry.get("run_id") or "")
        if not attempt_id or not variant_id or (variant_id, run_id) in archived:
            continue
        if str(entry.get("finalization_state") or "").upper() != "COMPLETE":
            continue
        payload = _present_indexed_result(
            root,
            entry,
            expected_campaign_id=campaign_id,
            expected_variant_id=variant_id,
        )
        payload["attempt_id"] = attempt_id
        payload["attempt_kind"] = entry.get("attempt_kind")
        payload["updated_at"] = entry.get("updated_at")
        result.setdefault(attempt_id, {})[variant_id] = payload
    return result


def _indexed_result_entry(
    root: Path,
    campaign_id: str,
    attempt_id: str,
    variant_id: str,
) -> Mapping[str, Any]:
    index_path = (
        load_storage_layout(root).active_campaign_root
        / campaign_id
        / "results_index.yaml"
    )
    source = _yaml_mapping(index_path)
    runs = source.get("runs") if isinstance(source.get("runs"), list) else []
    matches = [
        entry
        for entry in runs
        if isinstance(entry, Mapping)
        and str(entry.get("attempt_id") or "") == attempt_id
        and str(entry.get("variant_id") or "") == variant_id
        and str(entry.get("finalization_state") or "").upper() == "COMPLETE"
    ]
    if not matches:
        raise FileNotFoundError(
            f"no complete finalized result for attempt {attempt_id!r}, variant {variant_id!r}"
        )
    return matches[-1]


def _dataset_manager_detail(root: Path, dataset_id: str) -> dict[str, Any]:
    import pandas as pd

    manifest = next(
        (
            item
            for item in list_dataset_manifests(root)
            if str(item.get("dataset_id") or "") == dataset_id
        ),
        None,
    )
    if manifest is None:
        raise FileNotFoundError(f"governed dataset manifest not found: {dataset_id}")
    dataset_root = (
        load_storage_layout(root).dataset_root / dataset_id
    ).resolve()
    manifest_path = dataset_root / "dataset_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"governed dataset manifest is missing: {dataset_id}")
    roll_preview: list[dict[str, Any]] = []
    roll_status: dict[str, Any] = {
        "available": False,
        "reason": "dataset does not declare an explicit roll calendar",
    }
    relative_roll = str(manifest.get("roll_calendar") or "").strip()
    expected_roll_hash = str(manifest.get("roll_calendar_sha256") or "").strip()
    if relative_roll and expected_roll_hash:
        roll_path = resolve_recorded_path(relative_roll, project_root=root).resolve()
        if roll_path.is_relative_to(dataset_root) and roll_path.is_file():
            digest = hashlib.sha256(roll_path.read_bytes()).hexdigest()
            if digest == expected_roll_hash:
                roll_frame = pd.read_csv(roll_path)
                roll_preview = json.loads(
                    roll_frame.head(200).to_json(orient="records", date_format="iso")
                )
                roll_status = {
                    "available": True,
                    "rows": len(roll_frame),
                    "sha256": digest,
                    "truncated": len(roll_frame) > len(roll_preview),
                }
            else:
                roll_status = {
                    "available": False,
                    "reason": "roll-calendar hash is stale or mismatched",
                }
        else:
            roll_status = {
                "available": False,
                "reason": "roll-calendar path is missing or outside its governed dataset root",
            }
    return {
        "dataset_id": dataset_id,
        "manifest": manifest,
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "quality": {
            "verdict": manifest.get("quality_verdict"),
            "notes": manifest.get("quality_notes") or [],
            "defects": {
                name: int(manifest.get(name) or 0)
                for name in (
                    "dropped_row_count",
                    "gap_count",
                    "duplicate_count",
                    "out_of_order_count",
                    "invalid_ohlc_count",
                    "cadence_violation_count",
                )
            },
        },
        "coverage": {
            "start": manifest.get("coverage_start"),
            "end": manifest.get("coverage_end"),
            "rows": manifest.get("row_count"),
            "timezone": manifest.get("exchange_timezone") or manifest.get("timezone"),
            "timestamp_semantics": manifest.get("timestamp_semantics"),
        },
        "contracts": {
            "count": manifest.get("contract_count"),
            "column": manifest.get("contract_column"),
            "roll_policy": manifest.get("roll_policy"),
            "continuous_contract": manifest.get("continuous_contract"),
        },
        "roll_calendar": {**roll_status, "preview_rows": roll_preview},
        "vendor_comparison": {
            "available": False,
            "reason": (
                "Select another governed dataset in the library to run a manifest-level comparison; "
                "bar-for-bar equivalence remains a separate validation task."
            ),
        },
    }


def _resolve_current_work_scope(
    root: Path,
    campaign_id: str,
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Resolve active sequential work independently from lineage recency.

    The authored ``original`` attempt advances when a reviewed terminal FAIL
    installs the next sequential variant.  A later-created historical follow-up
    for an older variant remains immutable evidence, but must not take active
    workflow ownership away from that newer authored variant.
    """

    if not attempts:
        return {}
    service = FollowUpAttemptService(root)
    latest = dict(attempts[-1])
    try:
        active_variant_id = service.target_config_path(
            campaign_id,
            "original",
        ).parent.name
    except (FileNotFoundError, KeyError, OSError, ValueError):
        active_variant_id = str(latest.get("target_variant_id") or "")

    selected: dict[str, Any] | None = None
    selected_variant_id = ""
    for attempt in reversed(attempts):
        attempt_id = str(attempt.get("attempt_id") or "original")
        target_variant_id = str(attempt.get("target_variant_id") or "")
        if not target_variant_id:
            try:
                target_variant_id = service.target_config_path(
                    campaign_id,
                    attempt_id,
                ).parent.name
            except (FileNotFoundError, KeyError, OSError, ValueError):
                target_variant_id = ""
        if not active_variant_id or target_variant_id == active_variant_id:
            selected = dict(attempt)
            selected_variant_id = target_variant_id
            break

    if selected is None:
        selected = latest
        selected_variant_id = str(selected.get("target_variant_id") or "")
    selected["target_variant_id"] = selected_variant_id or active_variant_id
    selected["latest_attempt_id"] = str(
        latest.get("attempt_id") or "original"
    )
    selected["latest_attempt_kind"] = str(
        latest.get("attempt_kind") or "original"
    )
    selected["latest_attempt_label"] = _friendly_attempt_label(latest)
    return selected


def _campaign_workflow_context(
    campaign: Mapping[str, Any],
    attempts: list[dict[str, Any]],
    mechanics_approval: Mapping[str, Any],
    attempt_results: Mapping[str, Any],
    *,
    current_scope: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve one current attempt, target variant, gate, and primary action."""

    if not attempts:
        return {
            "current_attempt_id": None,
            "current_attempt_label": "No immutable attempt",
            "target_variant_id": None,
            "stage": "engineering_review",
            "scientific_status": "NEEDS MANUAL REVIEW",
            "primary_action": {
                "label": str(
                    campaign.get("workflow_blocker")
                    or "Engineering review is required."
                ),
                "section": "overview",
            },
        }

    current = dict(current_scope or attempts[-1])
    latest = attempts[-1]
    attempt_id = str(current.get("attempt_id") or "original")
    gate = mechanics_approval.get(attempt_id) or {}
    variants = gate.get("variants") if isinstance(gate.get("variants"), list) else []
    target_variant = str(
        current.get("target_variant_id")
        or next(
            (
                item.get("variant_id")
                for item in reversed(variants)
                if isinstance(item, Mapping) and item.get("variant_id")
            ),
            "",
        )
        or "v01"
    )
    target_gate = next(
        (
            item
            for item in variants
            if isinstance(item, Mapping)
            and str(item.get("variant_id") or "") == target_variant
        ),
        {},
    )
    progress = (
        target_gate.get("review_progress")
        if isinstance(target_gate.get("review_progress"), Mapping)
        else {}
    )
    sampled = int(progress.get("sampled_count") or 0)
    unreviewed = int(progress.get("unreviewed_count") or 0)
    approved = bool(gate.get("all_approved"))
    exact_result = (
        (attempt_results.get(attempt_id) or {}).get(target_variant)
        if isinstance(attempt_results.get(attempt_id), Mapping)
        else None
    )

    # Once this exact immutable attempt has a finalized result, its pre-PnL
    # gate is historical evidence. Never send a terminal attempt backwards to
    # mechanics review merely because its package later became unavailable for
    # new work.
    if exact_result:
        status = str(
            exact_result.get("research_verdict")
            or exact_result.get("verdict")
            or "NEEDS MANUAL REVIEW"
        )
        label = f"Inspect the exact {target_variant} result for this attempt"
        section = "results"
        stage = "result_review"
    elif not approved:
        has_evidence = bool(progress.get("evidence_available")) and sampled > 0
        if has_evidence:
            label = (
                f"Review {unreviewed} remaining sampled trade"
                f"{'' if unreviewed == 1 else 's'}"
                if unreviewed
                else f"Complete mechanics decision for {sampled} sampled trades"
            )
            section = "reviews"
            stage = "mechanics_review"
        else:
            label = f"Generate mechanics evidence for {target_variant}"
            section = "testing"
            stage = "mechanics_evidence"
        status = "NEEDS MANUAL REVIEW"
    else:
        status = "PENDING"
        label = f"Run the approved test suite for {target_variant}"
        section = "testing"
        stage = "ready_for_testing"

    return {
        "current_attempt_id": attempt_id,
        "current_attempt_kind": str(current.get("attempt_kind") or "original"),
        "current_attempt_label": _friendly_attempt_label(current),
        "parent_attempt_id": current.get("parent_attempt_id"),
        "latest_attempt_id": str(latest.get("attempt_id") or "original"),
        "latest_attempt_kind": str(latest.get("attempt_kind") or "original"),
        "latest_attempt_label": _friendly_attempt_label(latest),
        "target_variant_id": target_variant,
        "mechanics_status": target_gate.get("status") or "NEEDS_REVIEW",
        "review_progress": dict(progress),
        "stage": stage,
        "scientific_status": status,
        "primary_action": {
            "label": label,
            "section": section,
            "campaign_id": campaign.get("campaign_id"),
            "attempt_id": attempt_id,
            "variant_id": target_variant,
        },
    }


_RESEARCH_FLOW_PREFIX = (
    {
        "id": "protocol_frozen",
        "label": "Protocol frozen",
        "phase": "Define",
        "description": "Hypothesis, execution rules, data, and parameter space are immutable.",
    },
    {
        "id": "mechanics_evidence",
        "label": "Mechanics evidence",
        "phase": "Validate mechanics",
        "description": "Deterministic sampled trades and required risk cases are generated.",
    },
    {
        "id": "mechanics_review",
        "label": "Mechanics approval",
        "phase": "Validate mechanics",
        "description": "A human reviewer verifies timing, fills, exits, and no-lookahead behavior.",
    },
)


def _account_assessment_rows(root: Path, campaign_id: str) -> list[dict[str, Any]]:
    """Load only hash-valid, repository-owned account suitability artifacts."""

    assessment_root = load_storage_layout(root).research_artifact_root / "account_evaluations"
    if not assessment_root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for manifest_path in sorted(assessment_root.rglob("evaluation_manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or str(manifest.get("campaign_id") or "") != campaign_id:
            continue
        if manifest.get("schema") != "alphaquest.account-assessment-manifest/v1":
            raise ValueError(f"unsupported account assessment manifest: {manifest_path}")
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, dict):
            raise ValueError(f"account assessment has no artifact inventory: {manifest_path}")
        for name, record in artifacts.items():
            artifact_path = manifest_path.parent / str(name)
            expected = str(record.get("sha256") or "") if isinstance(record, dict) else ""
            actual = hashlib.sha256(artifact_path.read_bytes()).hexdigest() if artifact_path.is_file() else ""
            if not expected or actual != expected:
                raise ValueError(f"account assessment artifact hash mismatch: {artifact_path}")
        deterministic = json.loads(
            (manifest_path.parent / "deterministic_summary.json").read_text(encoding="utf-8")
        )
        monte_carlo = json.loads(
            (manifest_path.parent / "monte_carlo_summary.json").read_text(encoding="utf-8")
        )
        profile = json.loads(
            (manifest_path.parent / "account_profile_snapshot.json").read_text(encoding="utf-8")
        )
        if str(profile.get("profile_sha256") or "") != str(manifest.get("profile_sha256") or ""):
            raise ValueError(f"account profile snapshot hash identity mismatch: {manifest_path}")
        public_manifest = {**manifest, "assessment_path": str(manifest_path.parent)}
        row = account_suitability_row(public_manifest, deterministic, monte_carlo)
        row.update(
            {
                "assessment_id": manifest.get("assessment_id"),
                "created_at": manifest.get("created_at"),
                "account_kind": (profile.get("identity") or {}).get("account_kind"),
                "profile_name": profile.get("name"),
                "recommended_tests": (profile.get("evaluation_policy") or {}).get("recommended_tests") or [],
                "expected_evaluation_fees_per_pass": monte_carlo.get("expected_evaluation_fees_per_pass"),
            }
        )
        rows.append(row)
    return sorted(rows, key=lambda item: str(item.get("created_at") or ""), reverse=True)

_RESEARCH_FLOW_SUFFIX = (
    {
        "id": "account_suitability",
        "label": "Destination account suitability",
        "phase": "Assess destination",
        "description": "Replay the valid evidence against one exact challenge, funded, or live-account profile.",
    },
    {
        "id": "candidate_review",
        "label": "Independent candidate review",
        "phase": "Decide",
        "description": "A performance PASS remains only a candidate until independent review.",
    },
)

_METHODOLOGY_STAGE_DESCRIPTIONS = {
    "limited_core_grid_test": "Check the predeclared parameter grid and reject narrow or weak neighborhoods.",
    "limited_monkey_test": "Require the declared strategy to beat matched random-entry baselines.",
    "walk_forward_analysis": "Select only in-sample parameters and stitch unseen out-of-sample windows.",
    "wfa_oos_monkey_test": "Stress the stitched walk-forward trades against matched random entries.",
    "wfa_oos_monte_carlo": "Estimate drawdown, loss, and account-breach risk from unseen trades.",
    "simulated_incubation_core": "Evaluate the frozen candidate on the secondary historical holdout.",
    "simulated_incubation_monkey": "Stress the secondary holdout result against random-entry paths.",
    "acceptance_oos_test": "Open the final locked holdout once; after this, only reject or promote.",
}


def _research_flow_definitions() -> list[dict[str, Any]]:
    methodology = [
        {
            "id": stage_id,
            "label": STAGE_LABELS.get(stage_id, stage_id.replace("_", " ").title()),
            "phase": "Test robustness",
            "description": _METHODOLOGY_STAGE_DESCRIPTIONS.get(
                stage_id,
                "Apply the repository-owned pass/fail gate to unseen evidence.",
            ),
        }
        for stage_id in DEFAULT_STAGE_ORDER
    ]
    return [
        *(dict(item) for item in _RESEARCH_FLOW_PREFIX),
        *methodology,
        *(dict(item) for item in _RESEARCH_FLOW_SUFFIX),
    ]


def _criterion_stage_status(result: Mapping[str, Any], stage_id: str) -> str | None:
    criteria = [
        item
        for item in result.get("stage_criteria") or []
        if isinstance(item, Mapping)
        and str(item.get("stage") or "") == stage_id
        and item.get("decision_role") == "scientific_validity"
    ]
    if not criteria:
        return None
    values = {str(item.get("result") or "NEEDS MANUAL REVIEW").upper() for item in criteria}
    if values == {"PASS"}:
        return "complete"
    if "FAIL" in values:
        return "failed"
    return "blocked"


def _variant_research_progress(
    row: Mapping[str, Any],
    result: Mapping[str, Any] | None,
    workflow: Mapping[str, Any],
    *,
    is_current: bool,
    account_evaluations: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    definitions = _research_flow_definitions()
    statuses = {item["id"]: "upcoming" for item in definitions}
    statuses["protocol_frozen"] = "complete"
    workflow_stage = str(workflow.get("stage") or "") if is_current else ""
    scientific_status = str(
        row.get("research verdict")
        or row.get("research_verdict")
        or (workflow.get("scientific_status") if is_current else None)
        or "PENDING"
    ).upper()
    operational_state = str(
        row.get("operational state") or row.get("operational_state") or "NOT_QUEUED"
    ).upper()
    current_stage_id = "mechanics_evidence"
    current_stage_label_override: str | None = None
    next_action: str

    if result:
        statuses["mechanics_evidence"] = "complete"
        statuses["mechanics_review"] = "complete"
        generic_verdict = str(
            result.get("research_verdict") or result.get("verdict") or scientific_status
        ).upper()
        validity_verdict = str(
            result.get("scientific_validity_verdict") or "NEEDS MANUAL REVIEW"
        ).upper()
        scientific_status = validity_verdict
        validity_unresolved = next(
            (
                str(item.get("stage") or "")
                for item in result.get("stage_criteria") or []
                if isinstance(item, Mapping)
                and item.get("decision_role") == "scientific_validity"
                and str(item.get("result") or "NEEDS MANUAL REVIEW").upper() != "PASS"
            ),
            "",
        )
        for stage_id in DEFAULT_STAGE_ORDER:
            observed = _criterion_stage_status(result, stage_id)
            if observed:
                statuses[stage_id] = observed
        if validity_verdict == "PASS":
            for stage_id in DEFAULT_STAGE_ORDER:
                statuses[stage_id] = "complete"
            if generic_verdict == "PASS":
                statuses["account_suitability"] = "not_applicable"
                statuses["candidate_review"] = "current"
                current_stage_id = "candidate_review"
                next_action = "Complete independent candidate review; a PASS is not approval to trade."
            else:
                matching_accounts = [
                    item
                    for item in (account_evaluations or [])
                    if str(item.get("variant_id") or "")
                    == str(row.get("variant") or row.get("variant_id") or "")
                    and (
                        str(item.get("attempt_id") or "") == str(result.get("run_id") or "")
                        or str(item.get("source_attempt_id") or "")
                        == str(workflow.get("current_attempt_id") or "")
                    )
                ]
                if any(str(item.get("verdict") or "").upper() == "PASS" for item in matching_accounts):
                    statuses["account_suitability"] = "complete"
                    statuses["candidate_review"] = "current"
                    current_stage_id = "candidate_review"
                    next_action = "Complete profile-scoped independent candidate review."
                else:
                    statuses["account_suitability"] = (
                        "failed" if matching_accounts else "current"
                    )
                    statuses["candidate_review"] = "locked"
                    current_stage_id = "account_suitability"
                    next_action = (
                        "Generic objectives did not pass. Assess the exact result against a named "
                        "challenge, funded, or live-account profile."
                    )
        elif validity_unresolved in DEFAULT_STAGE_ORDER:
            failed_index = DEFAULT_STAGE_ORDER.index(validity_unresolved)
            for stage_id in DEFAULT_STAGE_ORDER[:failed_index]:
                if statuses[stage_id] == "upcoming":
                    statuses[stage_id] = "complete"
            statuses[validity_unresolved] = (
                "failed" if validity_verdict == "FAIL" else "blocked"
            )
            for stage_id in DEFAULT_STAGE_ORDER[failed_index + 1 :]:
                statuses[stage_id] = (
                    "not_applicable" if validity_verdict == "FAIL" else "locked"
                )
            statuses["candidate_review"] = (
                "not_applicable" if validity_verdict == "FAIL" else "locked"
            )
            statuses["account_suitability"] = (
                "not_applicable" if validity_verdict == "FAIL" else "locked"
            )
            current_stage_id = validity_unresolved
            next_action = (
                f"Stopped at {STAGE_LABELS.get(validity_unresolved, validity_unresolved)}. Review the scientific-validity FAIL before any governed successor."
                if validity_verdict == "FAIL"
                else f"Resolve {STAGE_LABELS.get(validity_unresolved, validity_unresolved)} evidence before continuing."
            )
        else:
            first_stage = DEFAULT_STAGE_ORDER[0]
            statuses[first_stage] = "blocked"
            for stage_id in DEFAULT_STAGE_ORDER[1:]:
                statuses[stage_id] = "locked"
            statuses["candidate_review"] = "locked"
            statuses["account_suitability"] = "locked"
            current_stage_id = first_stage
            current_stage_label_override = "Result integrity review"
            next_action = (
                "Verify the finalized, hash-bound result before any scientific stage is credited."
            )
    elif is_current:
        if workflow_stage == "mechanics_evidence":
            statuses["mechanics_evidence"] = "current"
            statuses["mechanics_review"] = "locked"
            for stage_id in DEFAULT_STAGE_ORDER:
                statuses[stage_id] = "locked"
            statuses["candidate_review"] = "locked"
            statuses["account_suitability"] = "locked"
            current_stage_id = "mechanics_evidence"
        elif workflow_stage == "mechanics_review":
            statuses["mechanics_evidence"] = "complete"
            statuses["mechanics_review"] = "current"
            for stage_id in DEFAULT_STAGE_ORDER:
                statuses[stage_id] = "locked"
            statuses["candidate_review"] = "locked"
            statuses["account_suitability"] = "locked"
            current_stage_id = "mechanics_review"
        elif workflow_stage == "ready_for_testing":
            statuses["mechanics_evidence"] = "complete"
            statuses["mechanics_review"] = "complete"
            statuses[DEFAULT_STAGE_ORDER[0]] = "ready"
            for stage_id in DEFAULT_STAGE_ORDER[1:]:
                statuses[stage_id] = "locked"
            statuses["candidate_review"] = "locked"
            statuses["account_suitability"] = "locked"
            current_stage_id = DEFAULT_STAGE_ORDER[0]
        else:
            statuses["mechanics_evidence"] = "blocked"
            statuses["mechanics_review"] = "locked"
            for stage_id in DEFAULT_STAGE_ORDER:
                statuses[stage_id] = "locked"
            statuses["candidate_review"] = "locked"
            statuses["account_suitability"] = "locked"
            current_stage_id = "mechanics_evidence"
            current_stage_label_override = "Engineering review"
        next_action = str(
            (workflow.get("primary_action") or {}).get("label")
            or "Complete the current governed gate."
        )
    else:
        statuses["mechanics_evidence"] = "locked"
        statuses["mechanics_review"] = "locked"
        for stage_id in DEFAULT_STAGE_ORDER:
            statuses[stage_id] = "locked"
        statuses["candidate_review"] = "locked"
        statuses["account_suitability"] = "locked"
        current_stage_id = "mechanics_evidence"
        current_stage_label_override = "Waiting for sequential activation"
        next_action = "Locked: only the current sequential variant may advance."

    stages = [
        {
            **definition,
            "step": index + 1,
            "status": statuses[definition["id"]],
        }
        for index, definition in enumerate(definitions)
    ]
    current = next(
        (item for item in stages if item["id"] == current_stage_id),
        stages[0],
    )
    return {
        "variant_id": str(row.get("variant") or row.get("variant_id") or ""),
        "attempt_id": (
            workflow.get("current_attempt_id") if is_current else row.get("attempt_id")
        ),
        "is_current": is_current,
        "current_step": current["step"],
        "total_steps": len(stages),
        "current_stage_id": current_stage_id,
        "current_stage_label": current_stage_label_override or current["label"],
        "current_phase": current["phase"],
        "scientific_status": scientific_status,
        "generic_objective_status": (
            str(result.get("generic_objective_verdict") or result.get("research_verdict") or "PENDING").upper()
            if result
            else "PENDING"
        ),
        "operational_state": operational_state,
        "next_action": next_action,
        "stages": stages,
    }


def _campaign_research_progress(
    workflow: Mapping[str, Any],
    rows: list[dict[str, Any]],
    attempt_results: Mapping[str, Any],
    latest_results: Mapping[str, Any],
    account_evaluations: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    target_variant = str(workflow.get("target_variant_id") or "")
    current_attempt = str(workflow.get("current_attempt_id") or "")
    exact_results = (
        attempt_results.get(current_attempt)
        if isinstance(attempt_results.get(current_attempt), Mapping)
        else {}
    )
    row_variant_ids = [
        str(row.get("variant") or row.get("variant_id") or "")
        for row in rows
        if str(row.get("variant") or row.get("variant_id") or "")
    ]
    selected_variant = target_variant or next(
        (variant_id for variant_id in reversed(row_variant_ids) if variant_id in latest_results),
        row_variant_ids[-1] if row_variant_ids else "",
    )
    variants = []
    for row in rows:
        variant_id = str(row.get("variant") or row.get("variant_id") or "")
        if not variant_id:
            continue
        is_current = bool(selected_variant) and variant_id == selected_variant
        result = (
            exact_results.get(variant_id)
            if is_current and isinstance(exact_results, Mapping) and exact_results
            else latest_results.get(variant_id)
        )
        variants.append(
            _variant_research_progress(
                row,
                result if isinstance(result, Mapping) else None,
                workflow,
                is_current=is_current,
                account_evaluations=account_evaluations,
            )
        )
    campaign = next((item for item in variants if item["is_current"]), None)
    return {
        "campaign": dict(campaign) if campaign else None,
        "variants": variants,
        "flow_definition": _research_flow_definitions(),
    }


def _friendly_attempt_label(attempt: Mapping[str, Any]) -> str:
    attempt_id = str(attempt.get("attempt_id") or "original")
    kind = (
        str(attempt.get("attempt_kind") or "original")
        .replace("_", " ")
        .title()
        .replace("Pnl", "PnL")
    )
    created = str(attempt.get("created_at") or "")
    day = created[:10] if len(created) >= 10 else "date not recorded"
    short_id = attempt_id[-8:] if attempt_id != "original" else "original"
    return f"{kind} · {day} · {short_id}"


def _archived_run_keys(root: Path, campaign_id: str) -> set[tuple[str, str]]:
    import sqlite3

    database = load_storage_layout(root).catalog_root / "research_registry.sqlite"
    if not database.is_file():
        return set()
    try:
        with sqlite3.connect(database) as connection:
            return {
                (str(variant_id or ""), str(test_run_id or ""))
                for variant_id, test_run_id in connection.execute(
                    "SELECT variant_id, test_run_id FROM runs WHERE campaign_id = ? AND archived = 1",
                    (campaign_id,),
                )
            }
    except sqlite3.Error:
        return set()


def _results_matrix(root: Path, campaign_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    # This presenter is currently shared with the compatibility Streamlit shell;
    # it contains no framework calls and preserves the authoritative join rules.
    from alphaquest.dashboard.studio_app import _results_matrix_state

    return _results_matrix_state(root, campaign_id)


def _present_indexed_result(
    root: Path,
    entry: Mapping[str, Any],
    *,
    expected_campaign_id: str,
    expected_variant_id: str,
) -> dict[str, Any]:
    errors: list[str] = []
    bound_config_path: Path | None = None
    bundle_path = _indexed_bundle_path(root, entry, errors)
    inspection: dict[str, Any] = {"valid": False, "errors": errors, "bundle": None, "manifest": None}
    if bundle_path is not None and not errors:
        inspection = inspect_finalized_result(bundle_path)
        errors.extend(str(item) for item in inspection.get("errors") or [])
        manifest = inspection.get("manifest")
        source_config = str((manifest or {}).get("source_config") or "").strip()
        if not source_config:
            errors.append("finalization manifest does not bind a frozen source config")
        else:
            config_path = resolve_recorded_path(source_config, project_root=root)
            if not config_path.is_file():
                errors.append("finalized source config is missing")
            else:
                context = resolve_campaign_context(config_path, project_root=root)
                if context is None or context.campaign_id != expected_campaign_id:
                    errors.append("finalized source config is outside the selected governed campaign")
                elif config_path.name != "config.yaml" or config_path.parent.name != expected_variant_id:
                    errors.append("finalized source config does not identify the selected variant")
                else:
                    bound_config_path = config_path
                    rebound = inspect_finalized_result(bundle_path, config_path=config_path)
                    errors.extend(str(item) for item in rebound.get("errors") or [])
                    inspection = rebound

    bundle = inspection.get("bundle")
    if not isinstance(bundle, ResultBundleV2):
        errors.append("strict ResultBundleV2 is unavailable")
    else:
        if bundle.campaign_id != expected_campaign_id:
            errors.append("ResultBundleV2 campaign identity does not match the selected campaign")
        if bundle.variant_id != expected_variant_id:
            errors.append("ResultBundleV2 variant identity does not match the selected variant")
        indexed_run_id = str(entry.get("test_run_id") or entry.get("run_id") or "").strip()
        if indexed_run_id and bundle.run_id != indexed_run_id:
            errors.append("ResultBundleV2 run identity does not match the source index")

    errors = list(dict.fromkeys(errors))
    if errors or not inspection.get("valid") or not isinstance(bundle, ResultBundleV2):
        return _manual_review_result(
            expected_campaign_id,
            expected_variant_id,
            run_id=str(entry.get("test_run_id") or entry.get("run_id") or "") or None,
            errors=errors or ["finalization validation did not pass"],
        )
    payload = bundle.model_dump(mode="json", by_alias=True)
    ratification = inspection.get("scientific_ratification")
    if isinstance(ratification, Mapping):
        payload["scientific_validity_verdict"] = ratification[
            "scientific_validity_verdict"
        ]
        metric_overrides = ratification.get("metric_overrides")
        if isinstance(metric_overrides, Mapping):
            payload["metrics"] = dict(metric_overrides)
        payload["verdict_message"] = str(
            ratification.get("verdict_message") or payload.get("verdict_message") or ""
        )
        payload["scientific_ratification"] = dict(ratification)
    artifact_previews = _result_artifact_previews(bundle, bundle_path)
    return {
        **payload,
        "research_verdict": bundle.verdict,
        "first_failed_or_unresolved_gate": _first_unresolved_bundle_gate(bundle),
        "finalization": {"valid": True, "errors": []},
        "source_index_verdict": entry.get("research_verdict"),
        "artifact_previews": artifact_previews,
        "core_grid_inspection": _core_grid_inspection(bound_config_path, artifact_previews),
    }


def _indexed_bundle_path(root: Path, entry: Mapping[str, Any], errors: list[str]) -> Path | None:
    value = str(entry.get("result_bundle_path") or "").strip()
    if value:
        path = resolve_recorded_path(value, project_root=root)
    else:
        run_value = str(entry.get("run_dir") or entry.get("output_dir") or "").strip()
        if not run_value:
            errors.append("source index does not identify a finalized ResultBundleV2")
            return None
        path = resolve_recorded_path(run_value, project_root=root) / "reporting_v2" / RESULT_BUNDLE_FILENAME
    path = path.resolve()
    evidence_roots = tuple(item.resolve() for item in load_storage_layout(root).evidence_roots)
    if not any(path.is_relative_to(evidence_root) for evidence_root in evidence_roots):
        errors.append("ResultBundleV2 pointer is outside configured evidence roots")
        return None
    if path.name != RESULT_BUNDLE_FILENAME or path.parent.name != "reporting_v2":
        errors.append("source index does not point to the canonical ResultBundleV2 location")
        return None
    if not path.is_file():
        errors.append("finalized ResultBundleV2 file is missing")
        return None
    return path


def _manual_review_result(
    campaign_id: str,
    variant_id: str,
    *,
    run_id: str | None,
    errors: list[str],
) -> dict[str, Any]:
    return {
        "schema": "alphaquest.result-presentation/v1",
        "campaign_id": campaign_id,
        "variant_id": variant_id,
        "run_id": run_id,
        "verdict": "NEEDS MANUAL REVIEW",
        "research_verdict": "NEEDS MANUAL REVIEW",
        "verdict_message": (
            "NEEDS MANUAL REVIEW — no complete hash-valid ResultBundleV2 transaction is available. "
            "Responsible next action: inspect preserved evidence and finalization recovery state; do not sign or replay this attempt."
        ),
        "metrics": {},
        "stage_criteria": [],
        "breakdowns": None,
        "supplemental_artifacts": None,
        "analysis_artifacts": None,
        "artifact_previews": {},
        "first_failed_or_unresolved_gate": "result_bundle_v2_finalization",
        "finalization": {"valid": False, "errors": errors},
    }


def _result_artifact_previews(bundle: ResultBundleV2, bundle_path: Path) -> dict[str, dict[str, Any]]:
    """Read hash-bound report CSVs for safe in-Studio review.

    The browser never receives a workstation path or arbitrary file endpoint.
    Curves are deterministically downsampled for display while their complete
    row counts and hashes remain visible from ResultBundleV2.
    """

    import json

    import pandas as pd

    statuses = {
        **bundle.breakdowns.model_dump(mode="json"),
        **bundle.supplemental_artifacts.model_dump(mode="json"),
        **bundle.analysis_artifacts.model_dump(mode="json"),
    }
    report_root = bundle_path.parent.resolve()
    previews: dict[str, dict[str, Any]] = {}
    for name, status in statuses.items():
        item = dict(status)
        item.update({"columns": [], "preview_rows": [], "truncated": False})
        relative = status.get("path")
        if not status.get("available") or not relative:
            previews[name] = item
            continue
        path = (report_root / str(relative)).resolve()
        if not path.is_relative_to(report_root) or path.suffix.casefold() != ".csv" or not path.is_file():
            item.update(
                {
                    "available": False,
                    "reason": "hash-bound report artifact is missing or outside its finalized report root",
                }
            )
            previews[name] = item
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != status.get("sha256"):
            item.update({"available": False, "reason": "report artifact hash is stale or mismatched"})
            previews[name] = item
            continue
        frame = pd.read_csv(path)
        limit = 500
        if len(frame) > limit:
            positions = sorted({round(index * (len(frame) - 1) / (limit - 1)) for index in range(limit)})
            preview = frame.iloc[positions]
            item["truncated"] = True
        else:
            preview = frame
        item["columns"] = [str(column) for column in frame.columns]
        item["preview_rows"] = json.loads(preview.to_json(orient="records", date_format="iso"))
        previews[name] = item
    return previews


def _core_grid_inspection(
    config_path: Path | None,
    artifact_previews: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Bind the browser's default grid selection to the frozen source config."""

    unavailable: dict[str, Any] = {
        "available": False,
        "reason": "declared-default core-grid identity is unavailable",
        "default_run_id": None,
        "declared_default_parameters": {},
        "parameter_columns": [],
        "iteration_count": 0,
        "iteration_reports_retained": False,
    }
    preview = artifact_previews.get("parameter_neighbors") or {}
    if config_path is None or not config_path.is_file():
        return unavailable
    if not preview.get("available"):
        return {**unavailable, "reason": str(preview.get("reason") or unavailable["reason"])}
    if preview.get("truncated"):
        return {
            **unavailable,
            "reason": "parameter-neighbor evidence is truncated; default iteration selection is disabled",
        }
    rows = preview.get("preview_rows")
    if not isinstance(rows, list) or not rows:
        return {**unavailable, "reason": "parameter-neighbor evidence has no inspectable rows"}

    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {**unavailable, "reason": "hash-bound source config could not be read"}
    if not isinstance(loaded, Mapping):
        return {**unavailable, "reason": "hash-bound source config is not a mapping"}
    core_grid = loaded.get("core_grid")
    strategy = loaded.get("strategy")
    if not isinstance(core_grid, Mapping) or not isinstance(strategy, Mapping):
        return {**unavailable, "reason": "hash-bound source config lacks strategy or core-grid definitions"}
    parameters = core_grid.get("parameters")
    if not isinstance(parameters, Mapping) or not parameters:
        return {
            **unavailable,
            "reason": "the core grid is a single fixed configuration and has no iteration selector",
            "iteration_count": len(rows),
            "iteration_reports_retained": bool(core_grid.get("retain_iteration_reports", False)),
        }

    defaults: dict[str, Any] = {}
    for parameter_path in parameters:
        value = _strategy_parameter_value(strategy, str(parameter_path))
        if value is _MISSING:
            return {
                **unavailable,
                "reason": f"declared default is missing for {parameter_path}",
                "parameter_columns": [str(item) for item in parameters],
                "iteration_count": len(rows),
                "iteration_reports_retained": bool(core_grid.get("retain_iteration_reports", False)),
            }
        defaults[str(parameter_path)] = value

    matches = [
        row
        for row in rows
        if isinstance(row, Mapping)
        and all(_parameter_values_equal(row.get(name, _MISSING), value) for name, value in defaults.items())
    ]
    if len(matches) != 1 or matches[0].get("run_id") is None:
        return {
            **unavailable,
            "reason": "declared defaults do not identify exactly one core-grid iteration",
            "declared_default_parameters": defaults,
            "parameter_columns": list(defaults),
            "iteration_count": len(rows),
            "iteration_reports_retained": bool(core_grid.get("retain_iteration_reports", False)),
        }
    return {
        "available": True,
        "reason": None,
        "default_run_id": matches[0]["run_id"],
        "declared_default_parameters": defaults,
        "parameter_columns": list(defaults),
        "iteration_count": len(rows),
        "iteration_reports_retained": bool(core_grid.get("retain_iteration_reports", False)),
        "metrics_source": "limited_core_grid_test/core_grid_results.csv",
        "default_metrics_scope": "declared_default_fixed_config",
    }


_MISSING = object()


def _strategy_parameter_value(strategy: Mapping[str, Any], parameter_path: str) -> Any:
    parts = parameter_path.split(".")
    if parts and parts[0] == "strategy":
        parts = parts[1:]
    value: Any = strategy
    for part in parts:
        if not isinstance(value, Mapping) or part not in value:
            return _MISSING
        value = value[part]
    return value


def _parameter_values_equal(actual: Any, expected: Any) -> bool:
    if actual is _MISSING:
        return False
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return float(actual) == float(expected)
    return actual == expected


def _first_unresolved_bundle_gate(bundle: ResultBundleV2) -> str:
    for criterion in bundle.stage_criteria:
        if criterion.result != "PASS":
            return criterion.stage
    return "none" if bundle.verdict == "PASS" else "result_bundle_v2_verdict"


def _campaign_next_action(campaign: Mapping[str, Any], rows: list[dict[str, Any]]) -> str:
    if not campaign.get("studio_managed"):
        return str(campaign.get("workflow_blocker") or "Engineering review is required.")
    if any(item.get("first failed or unresolved gate") == "result_bundle_v2_finalization" for item in rows):
        return (
            "Inspect the preserved evidence and finalization recovery state; "
            "do not sign, replay, or reuse the reserved attempt."
        )
    unresolved = [item for item in rows if item.get("research verdict") in {"PENDING", "NEEDS MANUAL REVIEW"}]
    if unresolved:
        return "Complete mechanics evidence and review for every frozen variant."
    if any(item.get("research verdict") == "PASS" for item in rows):
        return "Assign an independent candidate reviewer; PASS means candidate strategy only."
    return "Review the first failed gate before deciding whether a governed follow-up is scientifically warranted."


def _campaign_disclosure(
    root: Path,
    campaign_summary: Mapping[str, Any],
    attempts: list[dict[str, Any]],
    mechanics_approval: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build reviewer-facing, read-only protocol and immutable mechanics views.

    The browser receives normalized fields from governed source documents. It
    never receives an editable copy or a path that it can use to mutate source.
    """

    campaign_path = resolve_recorded_path(
        str(campaign_summary.get("path") or ""),
        project_root=root,
    )
    campaign_root = campaign_path.parent
    campaign = _yaml_mapping(campaign_path)
    spec = _yaml_mapping(campaign_root / "strategy_spec.yaml")
    fingerprint = (
        campaign.get("economic_edge_fingerprint")
        if isinstance(campaign.get("economic_edge_fingerprint"), Mapping)
        else {}
    )
    objectives = (
        campaign.get("research_objectives")
        if isinstance(campaign.get("research_objectives"), Mapping)
        else spec.get("research_objectives")
        if isinstance(spec.get("research_objectives"), Mapping)
        else {}
    )
    protocol = {
        "hypothesis": campaign.get("hypothesis") or spec.get("hypothesis"),
        "market_behavior": fingerprint.get("market_behavior"),
        "causal_mechanism": fingerprint.get("causal_mechanism")
        or spec.get("expected_mechanism"),
        "signal_inputs": _text_list(fingerprint.get("signal_inputs")),
        "market_context": fingerprint.get("market_context"),
        "holding_period": fingerprint.get("holding_period")
        or spec.get("holding_horizon"),
        "supporting_sources": [
            {
                "title": source.get("title"),
                "authors": source.get("authors"),
                "year": source.get("year"),
                "link": source.get("link"),
                "doi": source.get("doi"),
                "relevance": source.get("relevance"),
            }
            for source in campaign.get("sources") or []
            if isinstance(source, Mapping)
        ],
        "known_failure_modes": _text_list(spec.get("known_failure_modes")),
        "research_objectives": dict(objectives),
        "source_identity": {
            "campaign_id": campaign.get("campaign_id")
            or campaign_summary.get("campaign_id"),
            "governance_contract_version": campaign.get(
                "governance_contract_version"
            ),
            "frozen": spec.get("frozen") is True,
            "strategy_spec_schema": spec.get("schema"),
            "research_objectives_sha256": campaign.get("research_objectives_sha256")
            or spec.get("research_objectives_sha256"),
        },
    }

    distinctions = (
        campaign.get("variant_distinctions")
        if isinstance(campaign.get("variant_distinctions"), Mapping)
        else {}
    )
    histories = {
        str(item.get("variant_id") or ""): item
        for item in campaign.get("sequential_variant_history") or []
        if isinstance(item, Mapping) and item.get("variant_id")
    }
    spec_variants = {
        str(item.get("variant_id") or ""): item
        for item in spec.get("variants") or []
        if isinstance(item, Mapping) and item.get("variant_id")
    }
    service = FollowUpAttemptService(root)
    normalized_attempts = attempts or [
        {
            "attempt_id": "original",
            "attempt_kind": "original",
            "parent_attempt_id": None,
            "reason": "Frozen original campaign publication.",
        }
    ]
    attempt_rows: list[dict[str, Any]] = []
    variant_ids: set[str] = set()
    for attempt in normalized_attempts:
        attempt_id = str(attempt.get("attempt_id") or "original")
        try:
            paths = service.config_paths(
                str(campaign.get("campaign_id") or campaign_summary.get("campaign_id")),
                attempt_id,
            )
        except (FileNotFoundError, KeyError, OSError, ValueError) as exc:
            declared_variants = [
                str(
                    item
                    if isinstance(item, str)
                    else (item or {}).get("variant_id")
                    or (item or {}).get("id")
                    or ""
                )
                for item in campaign.get("variants") or []
            ]
            fallback_paths = tuple(
                campaign_root / "variants" / variant_id / "config.yaml"
                for variant_id in declared_variants
                if variant_id
            )
            if (
                attempt_id == "original"
                and fallback_paths
                and all(path.is_file() for path in fallback_paths)
            ):
                paths = fallback_paths
            else:
                attempt_rows.append(
                    {
                        "attempt_id": attempt_id,
                        "attempt_kind": attempt.get("attempt_kind") or "original",
                        "parent_attempt_id": attempt.get("parent_attempt_id"),
                        "reason": attempt.get("reason"),
                        "target_variant_id": attempt.get("target_variant_id"),
                        "created_at": attempt.get("created_at"),
                        "variants": [],
                        "source_error": str(exc),
                    }
                )
                continue

        target_variant_id = str(
            attempt.get("target_variant_id") or paths[-1].parent.name
        )
        approval_variants = {
            str(item.get("variant_id") or ""): item
            for item in (
                (mechanics_approval.get(attempt_id) or {}).get("variants") or []
            )
            if isinstance(item, Mapping)
        }
        variant_rows: list[dict[str, Any]] = []
        for path in paths:
            config = _yaml_mapping(path)
            variant_id = str(config.get("variant_id") or path.parent.name)
            variant_ids.add(variant_id)
            variant_spec = spec_variants.get(variant_id, {})
            rationales = (
                variant_spec.get("rationales")
                if isinstance(variant_spec.get("rationales"), Mapping)
                else {}
            )
            metadata = (
                config.get("research_metadata")
                if isinstance(config.get("research_metadata"), Mapping)
                else {}
            )
            review = (
                metadata.get("mechanics_review")
                if isinstance(metadata.get("mechanics_review"), Mapping)
                else {}
            )
            strategy = (
                config.get("strategy")
                if isinstance(config.get("strategy"), Mapping)
                else {}
            )
            event = (
                strategy.get("event")
                if isinstance(strategy.get("event"), Mapping)
                else {}
            )
            event_params = (
                event.get("params") if isinstance(event.get("params"), Mapping) else {}
            )
            if not event_params:
                entry = (
                    strategy.get("entry")
                    if isinstance(strategy.get("entry"), Mapping)
                    else {}
                )
                entry_params = (
                    entry.get("params")
                    if isinstance(entry.get("params"), Mapping)
                    else {}
                )
                event_params = (
                    entry_params.get("mechanics")
                    if isinstance(entry_params.get("mechanics"), Mapping)
                    else entry_params
                )
            core_grid = (
                config.get("core_grid")
                if isinstance(config.get("core_grid"), Mapping)
                else {}
            )
            parameter_grid = (
                core_grid.get("parameters")
                if isinstance(core_grid.get("parameters"), Mapping)
                else {}
            )
            distinction = (
                distinctions.get(variant_id)
                if isinstance(distinctions.get(variant_id), Mapping)
                else {}
            )
            history = histories.get(variant_id, {})
            certification = (
                config.get("strategy_certification")
                if isinstance(config.get("strategy_certification"), Mapping)
                else {}
            )
            entry_criteria: list[dict[str, Any]] = []
            try:
                from alphaquest.strategy_certification import (
                    get_strategy_certification,
                )

                current_certification = get_strategy_certification(
                    str(certification.get("strategy_id") or event.get("module") or ""),
                    root,
                    require_current=True,
                )
                current_identity = current_certification.public_record()
                if all(
                    certification.get(key) == current_identity.get(key)
                    for key in (
                        "strategy_id",
                        "implementation_version",
                        "implementation_sha256",
                        "manifest_sha256",
                    )
                ):
                    entry_criteria = [
                        dict(item)
                        for item in current_certification.studio.get(
                            "entry_criteria", []
                        )
                        if isinstance(item, Mapping)
                    ]
            except (KeyError, OSError, TypeError, ValueError):
                entry_criteria = []
            apex = (
                config.get("apex_rules")
                if isinstance(config.get("apex_rules"), Mapping)
                else {}
            )
            data = (
                config.get("data")
                if isinstance(config.get("data"), Mapping)
                else {}
            )
            execution_data = (
                data.get("execution_data")
                if isinstance(data.get("execution_data"), Mapping)
                else {}
            )
            is_target = variant_id == target_variant_id
            approval = approval_variants.get(variant_id, {}) if is_target else {}
            approval_status = (
                str(approval.get("status") or "NEEDS_MANUAL_REVIEW")
                if is_target
                else "INCLUDED_PREDECESSOR"
            )
            variant_rows.append(
                {
                    "variant_id": variant_id,
                    "title": variant_spec.get("title") or variant_id,
                    "is_attempt_target": is_target,
                    "config_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "mechanic_signature": metadata.get("mechanic_signature")
                    or distinction.get("mechanic_signature"),
                    "expresses_edge": review.get("mechanic_expresses_edge")
                    or rationales.get("mechanic")
                    or distinction.get("mechanic"),
                    "rules": {
                        "entry": review.get("entry_logic_rationale")
                        or rationales.get("entry"),
                        "stop": review.get("stop_loss_rationale")
                        or rationales.get("stop"),
                        "target_and_time_exit": review.get("target_exit_rationale")
                        or rationales.get("target"),
                        "forced_flatten": {
                            "timezone": apex.get("timezone")
                            or data.get("exchange_timezone"),
                            "latest_entry_time": apex.get("latest_entry_time"),
                            "flatten_time": apex.get("force_flatten_time")
                            or strategy.get("flatten_time"),
                            "latest_flat_time": apex.get("latest_flat_time"),
                            "overnight_allowed": not bool(
                                apex.get("no_overnight_positions", False)
                            ),
                        },
                    },
                    "causal_availability": metadata.get("timeframe_rationale")
                    or rationales.get("timeframe_session"),
                    "session_and_timeframe": {
                        "timeframe": config.get("timeframe")
                        or data.get("source_timeframe")
                        or campaign.get("timeframe"),
                        "timezone": data.get("exchange_timezone")
                        or apex.get("timezone"),
                        "session_start": execution_data.get("rth_start")
                        or data.get("rth_start"),
                        "session_end": execution_data.get("rth_end")
                        or data.get("rth_end"),
                        "rationale": metadata.get("timeframe_rationale")
                        or rationales.get("timeframe_session"),
                    },
                    "fixed_defaults": dict(event_params),
                    "entry_criteria": entry_criteria,
                    "parameter_grid": dict(parameter_grid),
                    "parameter_combination_count": _grid_combination_count(
                        parameter_grid
                    ),
                    "workload_forecast": workload_forecast(config),
                    "known_failure_modes": review.get("known_failure_modes"),
                    "material_difference": distinction.get(
                        "material_difference"
                    ),
                    "predecessor": (
                        {
                            "variant_id": history.get("predecessor_variant_id"),
                            "verdict": history.get("predecessor_verdict"),
                            "failure_analysis": history.get("failure_analysis"),
                            "result_path": history.get("predecessor_result_path"),
                            "result_sha256": history.get(
                                "predecessor_result_sha256"
                            ),
                        }
                        if history
                        else None
                    ),
                    "certification": {
                        "strategy_id": certification.get("strategy_id"),
                        "implementation_version": certification.get(
                            "implementation_version"
                        ),
                        "implementation_sha256": certification.get(
                            "implementation_sha256"
                        ),
                        "manifest_sha256": certification.get("manifest_sha256"),
                    },
                    "mechanics_approval": {
                        "status": approval_status,
                        "errors": [
                            str(item) for item in approval.get("errors") or []
                        ],
                        "note": (
                            "This is the target variant governed by this attempt."
                            if is_target
                            else "Same-campaign sequence context only; it is not mechanics, approval, or execution lineage for the target variant."
                        ),
                    },
                }
            )
        attempt_rows.append(
            {
                "attempt_id": attempt_id,
                "attempt_kind": attempt.get("attempt_kind") or "original",
                "parent_attempt_id": attempt.get("parent_attempt_id"),
                "reason": attempt.get("reason"),
                "target_variant_id": target_variant_id,
                "created_at": attempt.get("created_at"),
                "variants": variant_rows,
            }
        )

    legacy_action: dict[str, Any] = {
        "available": False,
        "parent_attempt_id": None,
        "target_variant_id": None,
        "unavailable_reason": "No immutable attempt is available.",
    }
    if attempt_rows:
        current_attempt = attempt_rows[-1]
        current_attempt_id = str(current_attempt.get("attempt_id") or "original")
        target_variant_id = str(current_attempt.get("target_variant_id") or "")
        current_config: dict[str, Any] = {}
        try:
            current_paths = service.config_paths(
                str(campaign.get("campaign_id") or campaign_summary.get("campaign_id")),
                current_attempt_id,
            )
            current_path = next(
                (
                    path
                    for path in current_paths
                    if path.parent.name == target_variant_id
                ),
                current_paths[-1],
            )
            current_config = _yaml_mapping(current_path)
            target_variant_id = str(
                current_config.get("variant_id") or current_path.parent.name
            )
        except (FileNotFoundError, KeyError, OSError, ValueError):
            current_config = {}
        current_objectives = current_config.get("research_objectives")
        current_objective_hash = current_config.get("research_objectives_sha256")
        destination_contract = current_config.get("destination_benchmark_contract")
        destination_hash = str(
            current_config.get("destination_benchmark_contract_sha256") or ""
        )
        if isinstance(destination_contract, Mapping) and destination_hash:
            computed_destination_hash = hashlib.sha256(
                json.dumps(
                    destination_contract,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()
            if computed_destination_hash == destination_hash:
                protocol["destination_benchmark_contract"] = dict(
                    destination_contract
                )
                protocol["source_identity"][
                    "destination_benchmark_contract_sha256"
                ] = destination_hash
        if isinstance(current_objectives, Mapping) and current_objective_hash:
            protocol["research_objectives"] = dict(current_objectives)
            protocol["source_identity"]["research_objectives_sha256"] = str(
                current_objective_hash
            )
            protocol["source_identity"]["research_objectives_attempt_id"] = (
                current_attempt_id
            )
            legacy_action = {
                "available": False,
                "parent_attempt_id": current_attempt_id,
                "target_variant_id": target_variant_id,
                "unavailable_reason": (
                    "The current attempt already has a frozen research-objective contract."
                ),
            }
        elif current_config:
            try:
                has_performance_evidence = service.parent_has_performance_evidence(
                    str(campaign.get("campaign_id") or campaign_summary.get("campaign_id")),
                    current_attempt_id,
                )
            except (FileNotFoundError, KeyError, OSError, ValueError):
                has_performance_evidence = True
            legacy_action = {
                "available": not has_performance_evidence,
                "parent_attempt_id": current_attempt_id,
                "target_variant_id": target_variant_id,
                "unavailable_reason": (
                    "This attempt already has performance evidence, so objectives cannot be retrofitted."
                    if has_performance_evidence
                    else None
                ),
            }
    protocol["legacy_pre_pnl_action"] = legacy_action
    return protocol, {
        "read_only": True,
        "variant_ids": sorted(variant_ids),
        "attempts": attempt_rows,
        "default_attempt_id": (
            str(attempt_rows[-1]["attempt_id"]) if attempt_rows else None
        ),
    }


def _yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value is None or not str(value).strip():
        return []
    return [str(value)]


def _grid_combination_count(parameters: Mapping[str, Any]) -> int:
    combinations = 1
    for values in parameters.values():
        combinations *= len(values) if isinstance(values, list) and values else 1
    return combinations


def _attempt_mechanics_gate(
    root: Path,
    campaign_id: str,
    attempts: list[dict[str, Any]],
    *,
    current_scope: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    from alphaquest.studio.approvals import MechanicsApprovalService

    follow_ups = FollowUpAttemptService(root)
    approvals = MechanicsApprovalService()
    from alphaquest.validation.promotion_gate import (
        inspect_historical_validation_approval,
    )

    try:
        finalized_results = _attempt_results(root, campaign_id)
    except Exception:
        finalized_results = {}
    result: dict[str, dict[str, Any]] = {}
    current_attempt_id = str(
        (current_scope or (attempts[-1] if attempts else {})).get("attempt_id")
        or ""
    )
    for attempt in attempts:
        attempt_id = str(attempt.get("attempt_id") or "")
        variants: list[dict[str, Any]] = []
        try:
            # Testing actions submit only the last/current variant frozen in
            # the selected attempt. Report the same scope here so an older
            # predecessor cannot keep the current variant's run button hidden.
            paths = (follow_ups.target_config_path(campaign_id, attempt_id),)
            for path in paths:
                if attempt_id != current_attempt_id:
                    variants.append(
                        {
                            "variant_id": path.parent.name,
                            "status": "HISTORICAL_IMMUTABLE",
                            "errors": [],
                            "review_progress": {},
                        }
                    )
                    continue
                try:
                    exact_result = (
                        (finalized_results.get(attempt_id) or {}).get(path.parent.name)
                        if isinstance(finalized_results.get(attempt_id), Mapping)
                        else None
                    )
                    if exact_result:
                        config = _yaml_mapping(path)
                        report = inspect_historical_validation_approval(config, path)
                    else:
                        report = approvals.inspect(path)
                    status = str(report.get("status") or "NEEDS_REVIEW")
                    errors = [str(item) for item in report.get("errors") or []]
                    review_progress: dict[str, Any] = {}
                    if not exact_result and attempt_id == current_attempt_id and status not in {
                        "APPROVED_FOR_TESTING",
                        "REJECTED",
                    }:
                        plan = approvals.plan(path, _gate_report=report)
                        review_progress = {
                            "evidence_available": bool(
                                plan.evidence_dir
                                and Path(plan.evidence_dir).is_dir()
                            ),
                            "sampled_count": len(plan.sampled_trade_ids),
                            "unreviewed_count": len(plan.unreviewed_trade_ids),
                            "non_correct_count": len(plan.non_correct_trade_ids),
                            "blocker_count": len(plan.blockers),
                            "ready_for_approval": plan.ready_for_approval,
                        }
                except Exception as exc:
                    status = "NEEDS_MANUAL_REVIEW"
                    errors = [str(exc)]
                    review_progress = {}
                variants.append(
                    {
                        "variant_id": path.parent.name,
                        "status": status,
                        "errors": errors,
                        "review_progress": review_progress,
                    }
                )
        except Exception as exc:
            variants = [
                {
                    "variant_id": None,
                    "status": "NEEDS_MANUAL_REVIEW",
                    "errors": [str(exc)],
                }
            ]
        unresolved = [
            item
            for item in variants
            if item.get("status") != "APPROVED_FOR_TESTING"
        ]
        result[attempt_id] = {
            "all_approved": bool(variants) and not unresolved,
            "approved_count": sum(
                item.get("status") == "APPROVED_FOR_TESTING" for item in variants
            ),
            "required_count": len(variants),
            "variants": variants,
            "blocker": (
                None
                if variants and not unresolved
                else "The selected attempt's target variant requires current mechanics approval before performance testing."
            ),
        }
    return result


def _mechanics_review_summaries(root: Path) -> list[dict[str, Any]]:
    from alphaquest.studio.approvals import MechanicsApprovalService

    service = FollowUpAttemptService(root)
    summaries: list[dict[str, Any]] = []
    input_hashes: dict[str, str] = {}
    for campaign in list_published_campaigns(root):
        if campaign.get("authored_lifecycle", campaign.get("lifecycle")) != "active" or not campaign.get(
            "studio_managed"
        ):
            continue
        campaign_id = str(campaign["campaign_id"])
        try:
            finalized_results = _attempt_results(root, campaign_id)
        except Exception:
            finalized_results = {}
        attempts = service.list_attempts(
            campaign_id,
            include_dataset_bindings=False,
        )
        current_scope = _resolve_current_work_scope(
            root,
            campaign_id,
            attempts,
        )
        current_attempt_id = str(current_scope.get("attempt_id") or "")
        current_variant_id = str(current_scope.get("target_variant_id") or "")
        paths_by_attempt: dict[str, tuple[Path, ...]] = {}
        for attempt in attempts:
            attempt_id = str(attempt["attempt_id"])
            try:
                paths_by_attempt[attempt_id] = service.config_paths(
                    campaign_id,
                    attempt_id,
                )
            except (FileNotFoundError, KeyError, OSError, ValueError):
                paths_by_attempt[attempt_id] = ()
        superseded_scopes = {
            (str(attempt.get("parent_attempt_id") or ""), path.parent.name)
            for attempt in attempts
            if attempt.get("parent_attempt_id")
            for path in paths_by_attempt.get(str(attempt["attempt_id"]), ())
        }
        for attempt in attempts:
            attempt_id = str(attempt["attempt_id"])
            available_paths = paths_by_attempt.get(attempt_id, ())
            target_variant_id = str(
                attempt.get("target_variant_id")
                or (available_paths[-1].parent.name if available_paths else "")
            )
            target_paths = tuple(
                path
                for path in available_paths
                if path.parent.name == target_variant_id
            )
            for path in target_paths[-1:]:
                if (attempt_id, path.parent.name) in superseded_scopes:
                    continue
                if (
                    isinstance(finalized_results.get(attempt_id), Mapping)
                    and path.parent.name in finalized_results[attempt_id]
                ):
                    # A PnL-bearing result makes this approval historical. Any
                    # result-integrity issue belongs in Results/Indexed
                    # Attention, never in the active mechanics queue.
                    continue
                try:
                    approval_service = MechanicsApprovalService()
                    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                    gate_cfg = (
                        ((cfg.get("research_metadata") or {}).get("validation_gate") or {})
                        if isinstance(cfg, dict)
                        else {}
                    )
                    input_identity = hashlib.sha256(
                        json.dumps(
                            {
                                "data": cfg.get("data") if isinstance(cfg, dict) else None,
                                "subset": gate_cfg.get("data_subset"),
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                            default=str,
                        ).encode("utf-8")
                    ).hexdigest()
                    gate = approval_service.inspect(
                        path,
                        precomputed_input_hash=input_hashes.get(input_identity),
                    )
                    observed_input_hash = str(gate.get("input_data_hash") or "")
                    if observed_input_hash:
                        input_hashes[input_identity] = observed_input_hash
                    if gate.get("status") in {"APPROVED_FOR_TESTING", "REJECTED"}:
                        continue
                    plan = approval_service.plan(path, _gate_report=gate)
                    payload = plan.model_dump(mode="json")
                except Exception as exc:
                    payload = {"config_path": str(path), "blockers": [str(exc)], "ready_for_approval": False}
                else:
                    payload["ready_for_approval"] = plan.ready_for_approval
                payload.update(
                    {
                        "review_id": f"{campaign_id}:{attempt_id}:{path.parent.name}",
                        "campaign_id": campaign_id,
                        "campaign_title": campaign.get("title") or campaign_id,
                        "attempt_id": attempt_id,
                        "variant_id": path.parent.name,
                        "attempt_kind": attempt.get("attempt_kind") or "original",
                        "attempt_label": _friendly_attempt_label(attempt),
                        "created_at": attempt.get("created_at"),
                        "is_current_workflow": (
                            attempt_id == current_attempt_id
                            and path.parent.name == current_variant_id
                        ),
                        "queue_scope": (
                            "current"
                            if attempt_id == current_attempt_id
                            and path.parent.name == current_variant_id
                            else "history"
                        ),
                    }
                )
                summaries.append(payload)
    summaries.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    summaries.sort(
        key=lambda item: (
            not bool(item.get("is_current_workflow")),
            not bool(item.get("ready_for_approval")),
        )
    )
    return summaries


def _workflow_stage_matrix(
    rows: list[dict[str, Any]],
    workflow: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Present the current attempt's real gate instead of a stale variant result."""

    target_variant = str(workflow.get("target_variant_id") or "")
    stage = str(workflow.get("stage") or "")
    if not target_variant or stage == "result_review":
        return rows

    progress = (
        workflow.get("review_progress")
        if isinstance(workflow.get("review_progress"), Mapping)
        else {}
    )
    reviewed = max(
        0,
        int(progress.get("sampled_count") or 0)
        - int(progress.get("unreviewed_count") or 0),
    )
    sampled = int(progress.get("sampled_count") or 0)
    gate_labels = {
        "mechanics_evidence": "mechanics evidence not generated",
        "mechanics_review": (
            f"mechanics review · {reviewed}/{sampled} sampled trades reviewed"
            if sampled
            else "mechanics review"
        ),
        "ready_for_testing": "mechanics approved · performance testing not run",
        "engineering_review": "engineering review",
    }
    current_row = {
        "variant": target_variant,
        "research verdict": str(
            workflow.get("scientific_status") or "NEEDS MANUAL REVIEW"
        ),
        "operational state": "NOT_QUEUED",
        "first failed or unresolved gate": gate_labels.get(stage, stage or "not run"),
        "diagnostic only": False,
        "run": workflow.get("current_attempt_id"),
        "attempt_id": workflow.get("current_attempt_id"),
        "current_workflow": True,
    }
    result = [
        dict(row)
        for row in rows
        if str(row.get("variant") or row.get("variant_id") or "") != target_variant
    ]
    result.append(current_row)
    return result


def _campaigns_with_workflow_context(
    root: Path,
    campaigns: list[dict[str, Any]],
    mechanics_reviews: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach the authoritative current stage to bootstrap campaign cards."""

    service = FollowUpAttemptService(root)
    review_by_campaign = {
        str(item.get("campaign_id") or ""): item
        for item in mechanics_reviews
        if item.get("is_current_workflow")
    }
    result: list[dict[str, Any]] = []
    for campaign in campaigns:
        row = dict(campaign)
        campaign_id = str(row.get("campaign_id") or "")
        if row.get("studio_managed"):
            try:
                attempts = service.list_attempts(
                    campaign_id,
                    include_dataset_bindings=False,
                )
            except Exception:
                attempts = []
        else:
            attempts = []
        current = _resolve_current_work_scope(root, campaign_id, attempts)
        latest_attempt = attempts[-1] if attempts else {}
        current_attempt_id = str(current.get("attempt_id") or "")
        current_variant_id = str(current.get("target_variant_id") or "")
        compact_review = review_by_campaign.get(campaign_id) or {}
        if (
            compact_review
            and str(compact_review.get("attempt_id") or "") == current_attempt_id
            and str(compact_review.get("variant_id") or "") == current_variant_id
        ):
            sampled = len(compact_review.get("sampled_trade_ids") or [])
            unreviewed = len(compact_review.get("unreviewed_trade_ids") or [])
            mechanics_approval = {
                current_attempt_id: {
                    "all_approved": False,
                    "variants": [
                        {
                            "variant_id": current_variant_id,
                            "status": "NEEDS_REVIEW",
                            "review_progress": {
                                "evidence_available": sampled > 0,
                                "sampled_count": sampled,
                                "unreviewed_count": unreviewed,
                                "non_correct_count": len(
                                    compact_review.get("non_correct_trade_ids") or []
                                ),
                                "blocker_count": len(compact_review.get("blockers") or []),
                                "ready_for_approval": bool(
                                    compact_review.get("ready_for_approval")
                                ),
                            },
                        }
                    ],
                }
            }
        else:
            try:
                mechanics_approval = _attempt_mechanics_gate(
                    root,
                    campaign_id,
                    attempts,
                    current_scope=current,
                )
            except Exception:
                mechanics_approval = {}
        try:
            rows, latest = _authoritative_results(root, campaign_id)
            exact_attempt_results = _attempt_results(root, campaign_id)
        except Exception:
            rows, latest, exact_attempt_results = [], {}, {}
        attempt_results: dict[str, dict[str, Any]] = exact_attempt_results
        workflow = _campaign_workflow_context(
            row,
            attempts,
            mechanics_approval,
            attempt_results,
            current_scope=current,
        )
        workflow_rows = _workflow_stage_matrix(rows, workflow)
        progress = _campaign_research_progress(
            workflow,
            workflow_rows,
            attempt_results,
            latest,
        )
        workflow["progress"] = progress.get("campaign") or {}
        row["current_attempt"] = workflow.get("current_attempt_id")
        if latest_attempt.get("created_at"):
            row["updated_at"] = latest_attempt.get("created_at")
        row["workflow_context"] = workflow
        row["research_progress"] = progress
        result.append(row)
    return result


def _candidate_review_summaries(root: Path) -> list[dict[str, Any]]:
    from alphaquest.studio.candidate_review import (
        CandidateReviewService,
        candidate_review_filename,
    )
    from alphaquest.studio.results import RESULT_BUNDLE_V3_FILENAME, load_result_bundle_v3

    rows: list[dict[str, Any]] = []
    layout = load_storage_layout(root)
    for evidence_root in layout.evidence_roots:
        for path in sorted(evidence_root.glob("**/reporting_v2/result_bundle_v2.json")):
            inspection = inspect_finalized_result(path)
            bundle = inspection.get("bundle")
            manifest = inspection.get("manifest") or {}
            campaign_id = str(
                (bundle.campaign_id if isinstance(bundle, ResultBundleV2) else None)
                or manifest.get("campaign_id")
                or "unknown"
            )
            variant_id = str(
                (bundle.variant_id if isinstance(bundle, ResultBundleV2) else None)
                or manifest.get("variant_id")
                or "unknown"
            )
            run_id = str(
                (bundle.run_id if isinstance(bundle, ResultBundleV2) else None)
                or manifest.get("run_id")
                or ""
            )
            presentation = _present_indexed_result(
                root,
                {"result_bundle_path": str(path), "test_run_id": run_id},
                expected_campaign_id=campaign_id,
                expected_variant_id=variant_id,
            )
            valid = bool((presentation.get("finalization") or {}).get("valid"))
            if not valid or not isinstance(bundle, ResultBundleV2):
                continue
            bases: list[dict[str, Any]] = []
            if bundle.scientific_validity_verdict == "PASS" and bundle.verdict == "PASS":
                bases.append(
                    {
                        "eligibility_basis": "generic_scientific_pass",
                        "account_assessment_id": None,
                        "result_bundle_v3_path": None,
                        "account_profile_id": None,
                        "account_profile_version": None,
                        "account_kind": None,
                        "account_verdict": None,
                    }
                )
            v3_path = path.parent / RESULT_BUNDLE_V3_FILENAME
            if bundle.scientific_validity_verdict == "PASS" and v3_path.is_file():
                try:
                    bundle_v3 = load_result_bundle_v3(v3_path)
                    if bundle_v3.result_bundle_v2_sha256 != hashlib.sha256(path.read_bytes()).hexdigest():
                        raise ValueError("ResultBundleV3 does not bind the current ResultBundleV2")
                    for binding in bundle_v3.account_evaluations:
                        if binding.destination_candidate_eligible:
                            bases.append(
                                {
                                    "eligibility_basis": "destination_specific_pass",
                                    "account_assessment_id": binding.assessment_id,
                                    "result_bundle_v3_path": str(v3_path),
                                    "account_profile_id": binding.profile_id,
                                    "account_profile_version": binding.profile_version,
                                    "account_kind": binding.account_kind,
                                    "account_verdict": binding.verdict,
                                }
                            )
                except (OSError, ValueError):
                    # Invalid account evidence is not reviewable and remains visible on Results.
                    pass
            for basis in bases:
                assessment_id = basis["account_assessment_id"]
                review_path = path.parent / candidate_review_filename(assessment_id)
                review_status = "required"
                review_blockers: list[str] = []
                if review_path.is_file():
                    source_config = resolve_recorded_path(
                        str(manifest.get("source_config") or ""),
                        project_root=root,
                    )
                    review_report = CandidateReviewService().inspect(
                        candidate_review_path=review_path,
                        result_bundle_path=path,
                        config_path=source_config,
                    )
                    if review_report.get("valid"):
                        continue
                    review_status = "invalid_or_stale"
                    review_blockers = [
                        "Existing candidate review is invalid or stale: " + str(error)
                        for error in review_report.get("errors") or ["verification did not pass"]
                    ]
                token = hashlib.sha256(path.read_bytes())
                if basis["result_bundle_v3_path"]:
                    token.update(v3_path.read_bytes())
                    token.update(str(assessment_id).encode("utf-8"))
                identity = f"{basis['eligibility_basis']}:{assessment_id or 'generic'}"
                rows.append(
                    {
                        "review_id": _review_id(path, identity),
                        "path": str(path),
                        "valid": valid,
                        "campaign_id": campaign_id,
                        "variant_id": variant_id,
                        "run_id": presentation.get("run_id") or run_id or None,
                        "verdict": presentation["research_verdict"],
                        "scientific_validity_verdict": bundle.scientific_validity_verdict,
                        "generic_objective_verdict": bundle.generic_objective_verdict,
                        "verdict_message": presentation["verdict_message"],
                        "errors": review_blockers,
                        "review_status": review_status,
                        "review_valid": False,
                        "review_blockers": review_blockers,
                        "evidence_token": token.hexdigest(),
                        "candidate_review_path": str(review_path) if review_path.is_file() else None,
                        "metrics": presentation.get("metrics") or {},
                        "stage_criteria": presentation.get("stage_criteria") or [],
                        "breakdowns": presentation.get("breakdowns"),
                        "supplemental_artifacts": presentation.get("supplemental_artifacts"),
                        "result_bundle": presentation,
                        **basis,
                    }
                )
    return rows


def _attempt_config(root: Path, campaign_id: str, attempt_id: str, variant_id: str) -> Path:
    paths = FollowUpAttemptService(root).config_paths(campaign_id, attempt_id)
    matches = [path for path in paths if path.parent.name == variant_id]
    if len(matches) != 1:
        raise FileNotFoundError("governed mechanics-review variant was not found")
    return matches[0]


def _finalization_recovery_job(
    root: Path,
    *,
    campaign_id: str,
    attempt_id: str,
    variant_id: str,
    config_path: Path,
) -> Any:
    layout = load_storage_layout(root)
    queue = SQLiteJobQueue(layout.studio_runtime_root / "jobs.sqlite3")
    candidates = [
        job
        for job in queue.list_jobs(limit=10_000)
        if job.job_type == "campaign_variant_run"
        and job.campaign_id == campaign_id
        and job.attempt_reserved
        and str(job.payload.get("attempt_id") or "") == attempt_id
        and str(job.payload.get("variant_id") or "") == variant_id
        and job.state == OperationalState.FAILED_OPERATIONAL
    ]
    if not candidates:
        raise ValueError(
            "no failed reserved campaign run is eligible for finalization-only recovery"
        )

    config_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
    eligible = []
    for job in candidates:
        recorded_config = str(job.payload.get("config_path") or "")
        recorded_output = str(job.payload.get("output_dir") or "")
        if not recorded_config or not recorded_output:
            continue
        if resolve_recorded_path(recorded_config, project_root=root).resolve() != config_path.resolve():
            continue
        if str(job.hash_locks.get("config_hash") or "") != config_hash:
            continue
        output = resolve_recorded_path(recorded_output, project_root=root).resolve()
        if not any(output.is_relative_to(base.resolve()) for base in layout.evidence_roots):
            continue
        manifest_path = output / "reporting_v2/finalization_manifest.json"
        marker_path = output / "studio_incomplete_attempt.json"
        archive_path = output / "studio_incomplete_attempt.recovered.json"
        if not manifest_path.is_file() or not (marker_path.is_file() or archive_path.is_file()):
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(manifest, Mapping) and str(manifest.get("job_id") or "") == job.job_id:
            eligible.append(job)
    if len(eligible) != 1:
        raise ValueError(
            "finalization-only recovery requires exactly one hash-bound failed run; "
            f"found {len(eligible)}"
        )
    return eligible[0]


def _recover_experiment_finalization(
    root: Path,
    *,
    cfg: Mapping[str, Any],
    result_bundle_path: Path,
    research_verdict: str,
) -> dict[str, Any]:
    layout = load_storage_layout(root)
    registry = ExperimentRegistry(
        layout.research_artifact_root / "governance" / "experiment_registry.jsonl"
    )
    identity = (
        str(cfg.get("campaign_id") or ""),
        str(cfg.get("variant_id") or ""),
        str(cfg.get("attempt_id") or ""),
    )
    result_sha256 = hashlib.sha256(result_bundle_path.read_bytes()).hexdigest()
    current = registry.current_status(*identity)
    if current == "COMPLETED":
        attempt = next(
            (
                item
                for item in registry.attempts()
                if (
                    str(item.get("campaign_id") or ""),
                    str(item.get("variant_id") or ""),
                    str(item.get("attempt_id") or ""),
                )
                == identity
            ),
            None,
        )
        resolution = (attempt or {}).get("resolution") or {}
        if (
            str(resolution.get("result_sha256") or "") != result_sha256
            or str(resolution.get("research_verdict") or "") != research_verdict
        ):
            raise ExperimentRegistryError(
                "completed experiment registry recovery does not bind the finalized result"
            )
        return {
            "status": "COMPLETED",
            "event_type": resolution.get("event_type"),
            "result_sha256": result_sha256,
            "idempotent_reuse": True,
        }
    if current != "FAILED":
        raise ExperimentRegistryError(
            f"finalization recovery requires FAILED or COMPLETED experiment state, found {current}"
        )
    prior = next(
        (
            event
            for event in reversed(registry.events())
            if event.get("event_type") == "ATTEMPT_RESOLVED"
            and (
                str(event.get("campaign_id") or ""),
                str(event.get("variant_id") or ""),
                str(event.get("attempt_id") or ""),
            )
            == identity
        ),
        None,
    )
    if prior is None or prior.get("result_sha256") is not None:
        raise ExperimentRegistryError(
            "failed experiment does not carry an unbound operational resolution eligible for recovery"
        )
    event = registry.recover_finalization(
        AttemptFinalizationRecovery(
            campaign_id=identity[0],
            variant_id=identity[1],
            attempt_id=identity[2],
            prior_resolution_sha256=str(prior.get("record_sha256") or ""),
            recorded_at=datetime.now(timezone.utc).isoformat(),
            reason=(
                "Explicit finalization-only recovery verified the frozen runner and reporting hashes; "
                "the PnL-bearing stages were not replayed."
            ),
            research_verdict=research_verdict,
            result_sha256=result_sha256,
        )
    )
    return {
        "status": "COMPLETED",
        "event_type": event.get("event_type"),
        "record_sha256": event.get("record_sha256"),
        "result_sha256": result_sha256,
        "idempotent_reuse": False,
    }


def _mechanics_review_detail(plan: Any, *, selected_trade_id: str | None = None) -> dict[str, Any]:
    payload = plan.model_dump(mode="json")
    payload["ready_for_approval"] = plan.ready_for_approval
    payload["sample_progress"] = {
        "required": len(plan.sampled_trade_ids),
        "reviewed_correct": len(plan.sampled_trade_ids)
        - len(plan.unreviewed_trade_ids)
        - len(plan.non_correct_trade_ids),
        "remaining": len(plan.unreviewed_trade_ids) + len(plan.non_correct_trade_ids),
    }
    payload["trade_evidence"] = None
    if not plan.evidence_dir or not plan.sampled_trade_ids:
        return payload

    selected = selected_trade_id or str(plan.sampled_trade_ids[0])
    allowed = {str(item) for item in plan.sampled_trade_ids}
    if selected not in allowed:
        raise ValueError("only a trade selected by the governed sampling plan may be inspected here")
    try:
        from alphaquest.dashboard.validation_app import (
            add_review_annotations,
            checklist_rows,
            exit_path_summary_frame,
            load_manual_reviews,
            orderflow_filter_explanations,
            prepare_trade_table,
            row_for_trade,
            rows_for_trade,
        )
        from alphaquest.validation import load_validation_run

        run = load_validation_run(plan.evidence_dir, include_tick_windows=False)
        reviews = load_manual_reviews(plan.evidence_dir)
        trades = add_review_annotations(
            prepare_trade_table(run.trades, run.exit_audits, run.validation_checks),
            reviews,
        )
        trade = row_for_trade(trades, selected)
        condition = row_for_trade(run.condition_snapshots, selected)
        exit_audit = row_for_trade(run.exit_audits, selected)
        bars = rows_for_trade(run.bar_windows, selected)
        events = _mechanics_event_timeline(run.event_transitions, selected)
        strategy_context = _mechanics_strategy_context(
            run.metadata,
            selected,
            Path(plan.config_path),
        )
        event_lane = str(run.metadata.get("validation_lane") or "").lower() == "event_replay"
        checks = run.validation_checks
        if not checks.empty and "trade_id" in checks.columns:
            identifiers = checks["trade_id"]
            checks = checks[identifiers.isna() | identifiers.astype(str).eq(selected)]
        annotation = row_for_trade(reviews, selected)
        payload["trade_evidence"] = {
            "trade_id": selected,
            "trade": _frame_record(trade),
            "bars": _frame_records(bars),
            "event_transitions": _frame_records(events),
            "strategy_context": strategy_context,
            "frozen_mechanics": _mechanics_frozen_parameters(Path(plan.config_path)),
            "condition_checklist": _frame_records(checklist_rows(condition)),
            "condition_snapshot": _frame_record(condition),
            "orderflow": _frame_records(orderflow_filter_explanations(condition)),
            "exit_path": [] if event_lane else _frame_records(exit_path_summary_frame(exit_audit)),
            "exit_audit": _frame_record(exit_audit),
            "automated_checks": _frame_records(checks),
            "annotation": _frame_record(annotation),
            "metadata": _json_safe_mapping(run.metadata),
        }
        payload["trade_evidence_token"] = hashlib.sha256(
            __import__("json")
            .dumps(
                payload["trade_evidence"],
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            .encode("utf-8")
        ).hexdigest()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        payload["trade_evidence_error"] = f"governed trade evidence could not be loaded: {exc}"
    return payload


def _mechanics_event_timeline(events: Any, trade_id: str) -> Any:
    """Return trade-linked transitions plus the causal order submission."""

    import pandas as pd

    if events is None or events.empty or "trade_id" not in events.columns:
        return pd.DataFrame()
    identifiers = events["trade_id"]
    selected_key = _mechanics_trade_id_key(trade_id)
    linked = events[
        identifiers.notna() & identifiers.map(_mechanics_trade_id_key).eq(selected_key)
    ].copy()
    if linked.empty or "transition" not in linked.columns:
        return linked
    entries = linked[linked["transition"].astype(str).eq("entry_filled")]
    if len(entries) != 1:
        return linked.sort_values(["event_index", "source_ordinal"], kind="stable")
    entry = entries.iloc[0]
    candidates = events.copy()
    for column in ("session_date", "contract", "order_id"):
        if column in candidates.columns and pd.notna(entry.get(column)):
            candidates = candidates[candidates[column].astype(str).eq(str(entry.get(column)))]
    event_indexes = pd.to_numeric(candidates.get("event_index"), errors="coerce")
    entry_index = pd.to_numeric(pd.Series([entry.get("event_index")]), errors="coerce").iloc[0]
    submissions = candidates[
        candidates["transition"].astype(str).eq("order_submitted") & event_indexes.lt(entry_index)
    ]
    if not submissions.empty:
        linked = pd.concat([submissions.sort_values("event_index").tail(1), linked], ignore_index=True)
    return linked.drop_duplicates(
        subset=["timestamp", "source_ordinal", "transition"],
        keep="last",
    ).sort_values(["event_index", "source_ordinal"], kind="stable")


def _mechanics_strategy_context(
    metadata: Mapping[str, Any],
    trade_id: str,
    config_path: Path,
) -> dict[str, Any] | None:
    """Load the immutable source trade row that contains strategy-specific trace fields."""

    import pandas as pd

    recorded = metadata.get("source_trade_log")
    if not recorded:
        return None
    source = Path(str(recorded))
    if not source.is_absolute():
        source = next(
            (parent / source for parent in config_path.resolve().parents if (parent / source).is_file()),
            Path.cwd() / source,
        )
    if not source.is_file():
        return None
    frame = pd.read_csv(source)
    if frame.empty or "trade_id" not in frame.columns:
        return None
    rows = frame[frame["trade_id"].astype(str).eq(str(trade_id))]
    if rows.empty:
        rows = frame[frame["trade_id"].map(_mechanics_trade_id_key).eq(_mechanics_trade_id_key(trade_id))]
    return _frame_record(None if rows.empty else rows.iloc[0])


def _mechanics_frozen_parameters(config_path: Path) -> dict[str, Any]:
    """Expose the exact frozen mechanics needed for trade-by-trade review.

    The browser receives a curated, read-only projection of the hash-bound
    config.  It does not infer configured values from a realized trade row.
    """

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"could not load frozen mechanics config: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("frozen mechanics config must contain a mapping")

    strategy = raw.get("strategy") or {}
    if not isinstance(strategy, Mapping):
        strategy = {}
    event = strategy.get("event") or {}
    if not isinstance(event, Mapping):
        event = {}
    event_params = event.get("params") or {}
    if not isinstance(event_params, Mapping):
        event_params = {}
    protocol = raw.get("apex_rules") or {}
    if not isinstance(protocol, Mapping):
        protocol = {}
    core = raw.get("core") or {}
    if not isinstance(core, Mapping):
        core = {}
    position_sizing = strategy.get("position_sizing") or core.get("position_sizing") or {}
    if not isinstance(position_sizing, Mapping):
        position_sizing = {}
    metadata = raw.get("research_metadata") or {}
    if not isinstance(metadata, Mapping):
        metadata = {}
    review_spec = metadata.get("mechanics_review") or {}
    if not isinstance(review_spec, Mapping):
        review_spec = {}

    def module_name(name: str) -> Any:
        component = strategy.get(name) or {}
        return component.get("module") if isinstance(component, Mapping) else None

    execution_keys = (
        "tick_value",
        "commission_per_contract",
        "slippage_ticks",
        "entry_slippage_ticks",
        "protective_stop_slippage_ticks",
        "target_limit_slippage_ticks",
        "market_exit_slippage_ticks",
        "signal_instrument",
        "execution_instrument",
        "entry_start",
        "latest_entry_time",
        "flatten_time",
        "max_trades_per_day",
        "event_stop_market_fill_policy",
    )
    execution = {
        key: strategy.get(key) if key in strategy else core.get(key)
        for key in execution_keys
        if key in strategy or key in core
    }
    execution["position_sizing"] = dict(position_sizing)
    for key in ("initial_balance", "tick_size", "point_value", "tick_value"):
        if key in core and key not in execution:
            execution[key] = core.get(key)

    return _json_safe_mapping(
        {
            "strategy_id": raw.get("strategy_name"),
            "variant_id": raw.get("variant_id"),
            "event_module": event.get("module"),
            "entry_module": module_name("entry"),
            "stop_module": module_name("sl"),
            "target_module": module_name("tp"),
            "event_parameters": dict(event_params),
            "execution": execution,
            "protocol": dict(protocol),
            "specification": dict(review_spec),
        }
    )


def _mechanics_trade_id_key(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(number)) if number.is_integer() else str(value)


def _frame_records(value: Any) -> list[dict[str, Any]]:
    """Convert a pandas frame to strict JSON records without NaN/Infinity."""

    if value is None or getattr(value, "empty", True):
        return []
    return list(__import__("json").loads(value.to_json(orient="records", date_format="iso")))


def _frame_record(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    frame = value.to_frame().T if hasattr(value, "to_frame") else value
    rows = _frame_records(frame)
    return rows[0] if rows else None


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    import json

    return dict(json.loads(json.dumps(dict(value), default=str, allow_nan=False)))


def _follow_up_options(root: Path, campaign_id: str, parent_attempt_id: str) -> dict[str, Any]:
    """Describe governed choices without exposing YAML editing to the browser."""

    import yaml
    from alphaquest.strategy_certification import (
        StrategyCertificationError,
        StrategyPackageAccess,
        get_strategy_certification,
    )

    service = FollowUpAttemptService(root)
    attempts = service.list_attempts(
        campaign_id,
        include_dataset_bindings=False,
    )
    if parent_attempt_id not in {str(item.get("attempt_id")) for item in attempts}:
        raise FileNotFoundError("selected parent attempt was not found")
    current_scope = _resolve_current_work_scope(root, campaign_id, attempts)
    selected_config_path = service.target_config_path(
        campaign_id,
        parent_attempt_id,
    )
    parameters: dict[str, list[dict[str, Any]]] = {}
    event_parameter_declarations: dict[str, list[dict[str, Any]]] = {}
    mechanics_validation_windows: dict[str, dict[str, Any]] = {}
    parent_new_work_allowed = True
    parent_new_work_reason: str | None = None
    parent_strategy_package: dict[str, Any] | None = None
    for path in (selected_config_path,):
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        mechanics_validation_windows[path.parent.name] = (
            service.fixed_mechanics_validation_window(config)
        )
        strategy = config.get("strategy") if isinstance(config, dict) else {}
        options: list[dict[str, Any]] = []
        for component in ("entry", "sl", "tp"):
            binding = strategy.get(component) if isinstance(strategy, dict) else None
            params = binding.get("params") if isinstance(binding, dict) else None
            if not isinstance(params, dict):
                continue
            for parameter_path, current in _scalar_parameter_options(params):
                options.append(
                    {
                        "component": component,
                        "module": binding.get("module"),
                        "parameter_path": parameter_path,
                        "current_value": current,
                        "value_type": _scalar_type(current),
                    }
                )
        parameters[path.parent.name] = options
        event = strategy.get("event") if isinstance(strategy, dict) and isinstance(strategy.get("event"), dict) else {}
        if event:
            certification = get_strategy_certification(
                str(event.get("module") or ""),
                root,
                require_current=True,
                access=StrategyPackageAccess.INSPECTION,
            )
            try:
                get_strategy_certification(
                    certification.strategy_id,
                    root,
                    require_current=True,
                    access=StrategyPackageAccess.NEW_WORK,
                )
            except StrategyCertificationError as exc:
                parent_new_work_allowed = False
                parent_new_work_reason = str(exc)
            parent_strategy_package = {
                "strategy_id": certification.strategy_id,
                "new_work_allowed": parent_new_work_allowed,
                "new_work_blocker": parent_new_work_reason,
            }
            current_params = event.get("params") if isinstance(event.get("params"), dict) else {}
            current_grid = (config.get("core_grid") or {}).get("parameters") or {}
            event_parameter_declarations[path.parent.name] = [
                {
                    "name": name,
                    **parameter.public_record(),
                    "current_value": current_params.get(name, parameter.default),
                    "selected_values": current_grid.get(f"event.params.{name}", []),
                }
                for name, parameter in certification.parameters.items()
            ]
    datasets = [
        {
            "dataset_id": item.get("dataset_id"),
            "symbol": item.get("symbol"),
            "timeframe": item.get("timeframe"),
            "quality_verdict": item.get("quality_verdict"),
        }
        for item in list_dataset_manifests(root)
        if item.get("quality_verdict") == "PASS"
    ]
    campaigns = {str(item["campaign_id"]): item for item in list_published_campaigns(root)}
    campaign = campaigns.get(campaign_id) or {}
    rescue_allowed = bool((campaign.get("rescue_policy") or {}).get("allowed"))
    has_performance_evidence = service.parent_has_performance_evidence(
        campaign_id,
        parent_attempt_id,
    )
    parent_attempts = _follow_up_parent_options(
        attempts,
        recommended_attempt_id=str(current_scope.get("attempt_id") or ""),
    )
    return {
        "attempt_kinds": _follow_up_kind_options(
            rescue_allowed=rescue_allowed,
            has_performance_evidence=has_performance_evidence,
            parent_new_work_allowed=parent_new_work_allowed,
            parent_new_work_reason=parent_new_work_reason,
        ),
        "parent_attempt_id": parent_attempt_id,
        "current_work_scope": {
            "attempt_id": current_scope.get("attempt_id"),
            "variant_id": current_scope.get("target_variant_id"),
            "latest_attempt_id": current_scope.get("latest_attempt_id"),
        },
        "parent_attempts": parent_attempts,
        "selected_parent": next(
            item for item in parent_attempts if item["attempt_id"] == parent_attempt_id
        ),
        "parameters": parameters,
        "event_parameter_declarations": event_parameter_declarations,
        "mechanics_validation_windows": mechanics_validation_windows,
        "datasets": datasets,
        "parent_strategy_package": parent_strategy_package,
        "rescue_allowed": rescue_allowed,
        "reason_min_length": 80,
    }


def _follow_up_kind_options(
    *,
    rescue_allowed: bool,
    has_performance_evidence: bool = False,
    parent_new_work_allowed: bool = True,
    parent_new_work_reason: str | None = None,
) -> list[dict[str, Any]]:
    options = [
        {
            "value": "replication",
            "label": "Exact replication",
            "summary": "Run the same frozen attempt again under a new immutable identity.",
            "use_when": (
                "The selected attempt was interrupted, operationally invalid, or needs an exact "
                "reproducibility check with no research change."
            ),
            "do_not_use_when": (
                "Do not use when data, mechanics, parameters, validation windows, or methodology must change."
            ),
            "parent_rule": (
                "Select the exact attempt you want to reproduce. The new attempt inherits that parent's "
                "strategy, data, parameter space, and methodology unchanged."
            ),
            "available": True,
        },
        {
            "value": "data_refresh",
            "label": "Governed data refresh",
            "summary": "Keep the research specification and replace only the governed dataset.",
            "use_when": (
                "A corrected source, refreshed coverage, contract-roll repair, or another governed data "
                "replacement is the only intended change."
            ),
            "do_not_use_when": "Do not use to change mechanics, parameters, or test methodology.",
            "parent_rule": (
                "Select the attempt whose strategy and methodology should carry forward. Usually this is "
                "the current leaf; the replacement dataset is applied relative to that exact parent."
            ),
            "available": True,
        },
        {
            "value": "methodology_rerun",
            "label": "Methodology rerun",
            "summary": "Keep strategy and performance tests frozen; replace the mechanics-review sample window.",
            "use_when": (
                "Fresh chart-review evidence is needed from a different bounded window while strategy "
                "mechanics, grids, data, and performance windows remain unchanged."
            ),
            "do_not_use_when": "Do not use merely to rerun performance or to alter the strategy.",
            "parent_rule": (
                "Select the attempt whose unchanged mechanics require fresh validation evidence. The child "
                "changes only that parent's mechanics-validation window."
            ),
            "available": True,
        },
        {
            "value": "pre_pnl_mechanics_correction",
            "label": "Pre-PnL mechanics correction",
            "summary": "Correct one reviewed mechanic before any performance evidence exists.",
            "use_when": (
                "Manual mechanics review found an implementation or reviewed scalar-value error before "
                "the selected attempt generated PnL."
            ),
            "do_not_use_when": (
                "Forbidden after performance evidence exists; this is a correction, not a response to results."
            ),
            "parent_rule": (
                "Select the exact pre-PnL attempt containing the mechanics error. It must have no performance "
                "evidence, and the correction branches from its frozen values."
            ),
            "available": not has_performance_evidence,
            "unavailable_reason": (
                "This parent already has performance evidence. Pre-PnL mechanics corrections are no longer allowed."
                if has_performance_evidence
                else None
            ),
        },
        {
            "value": "pre_pnl_parameter_declaration",
            "label": "Pre-PnL parameter declaration",
            "summary": "Declare the certified optimization grid before the first PnL-bearing test.",
            "use_when": (
                "Mechanics and reviewed defaults are frozen, but certified tunable dimensions still need "
                "to be predeclared for core grid and walk-forward analysis."
            ),
            "do_not_use_when": (
                "Forbidden after performance evidence exists and cannot widen a grid after seeing results."
            ),
            "parent_rule": (
                "Select the pre-PnL attempt whose certified defaults and mechanics the grid must include. "
                "It must have no performance evidence."
            ),
            "available": not has_performance_evidence,
            "unavailable_reason": (
                "This parent already has performance evidence. Its parameter space can no longer be declared or widened."
                if has_performance_evidence
                else None
            ),
        },
        {
            "value": "rescue",
            "label": "Authorized rescue",
            "summary": "Spend the campaign's one authorized rescue after a complete scientific FAIL.",
            "use_when": (
                "The exact target variant has a complete, hash-valid terminal FAIL and the campaign policy "
                "explicitly permits one logged rescue."
            ),
            "do_not_use_when": (
                "Do not use for interrupted, partial, PASS, pending, or NEEDS MANUAL REVIEW attempts."
            ),
            "parent_rule": (
                "Select the exact terminal FAIL being rescued—not an ancestor and not simply the newest attempt. "
                "The selected target variant must have complete finalized failure evidence."
            ),
            "available": rescue_allowed,
            "unavailable_reason": (
                None
                if rescue_allowed
                else "This campaign's frozen rescue policy does not authorize a rescue."
            ),
        },
    ]
    impacts = {
        "replication": {
            "changes": ["attempt identity", "fresh execution evidence"],
            "preserves": ["strategy mechanics", "dataset", "parameter grid", "methodology"],
            "invalidates": ["no source contract; a fresh result and review lifecycle are still required"],
        },
        "data_refresh": {
            "changes": ["dataset identity and input-data SHA-256", "fresh attempt evidence"],
            "preserves": ["strategy mechanics", "parameter grid", "methodology"],
            "invalidates": ["prior mechanics approval", "prior PnL evidence", "candidate approval"],
        },
        "methodology_rerun": {
            "changes": ["bounded mechanics-validation sample window", "validation evidence hashes"],
            "preserves": ["strategy mechanics", "dataset", "parameter grid", "performance windows"],
            "invalidates": ["prior mechanics approval for the child attempt"],
        },
        "pre_pnl_mechanics_correction": {
            "changes": ["one reviewed execution mechanic or certification identity"],
            "preserves": ["economic hypothesis", "prior immutable attempt"],
            "invalidates": ["validation evidence", "mechanics approval", "any stale certification binding"],
        },
        "pre_pnl_parameter_declaration": {
            "changes": ["predeclared certified parameter grid"],
            "preserves": ["reviewed default mechanics", "dataset", "economic hypothesis"],
            "invalidates": ["prior mechanics approval for the child attempt"],
        },
        "rescue": {
            "changes": ["authorized strategy expression and attempt identity"],
            "preserves": ["economic edge family", "failed predecessor evidence"],
            "invalidates": ["all predecessor approvals for the child mechanics", "prior performance evidence as promotion evidence"],
        },
    }
    for option in options:
        if (
            option["value"] != "replication"
            and not parent_new_work_allowed
        ):
            option["available"] = False
            existing_reason = str(option.get("unavailable_reason") or "").strip()
            lifecycle_reason = (
                parent_new_work_reason
                or "The selected parent strategy package is unavailable for new work."
            )
            option["unavailable_reason"] = " ".join(
                item for item in (existing_reason, lifecycle_reason) if item
            )
        option["impact_preview"] = impacts[str(option["value"])]
    return options


def _follow_up_parent_options(
    attempts: list[dict[str, Any]],
    *,
    recommended_attempt_id: str | None = None,
) -> list[dict[str, Any]]:
    child_counts: dict[str, int] = {}
    for attempt in attempts:
        parent_id = str(attempt.get("parent_attempt_id") or "")
        if parent_id:
            child_counts[parent_id] = child_counts.get(parent_id, 0) + 1
    leaves = [
        str(attempt.get("attempt_id") or "")
        for attempt in attempts
        if child_counts.get(str(attempt.get("attempt_id") or ""), 0) == 0
    ]
    recommended = (
        recommended_attempt_id
        if recommended_attempt_id
        and recommended_attempt_id
        in {str(item.get("attempt_id") or "") for item in attempts}
        else leaves[-1]
        if leaves
        else "original"
    )
    recommended_label = (
        "Recommended active work"
        if recommended_attempt_id and recommended == recommended_attempt_id
        else "Recommended current leaf"
    )
    result: list[dict[str, Any]] = []
    for attempt in attempts:
        attempt_id = str(attempt.get("attempt_id") or "")
        children = child_counts.get(attempt_id, 0)
        result.append(
            {
                "attempt_id": attempt_id,
                "attempt_kind": str(attempt.get("attempt_kind") or "original"),
                "parent_attempt_id": attempt.get("parent_attempt_id"),
                "reason": str(attempt.get("reason") or ""),
                "created_at": attempt.get("created_at"),
                "child_count": children,
                "is_leaf": children == 0,
                "recommended": attempt_id == recommended,
                "lineage_label": (
                    recommended_label
                    if attempt_id == recommended
                    else "Available leaf"
                    if children == 0
                    else f"Earlier branch point with {children} follow-up"
                    + ("" if children == 1 else "s")
                ),
                "branch_warning": (
                    None
                    if children == 0
                    else (
                        "This attempt already has a follow-up. Choosing it creates a separate branch from "
                        "this earlier frozen state; changes in its existing descendants will not be inherited."
                    )
                ),
            }
        )
    return result


def _scalar_parameter_options(value: Mapping[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    for name, item in value.items():
        path = f"{prefix}.{name}" if prefix else str(name)
        if isinstance(item, Mapping):
            rows.extend(_scalar_parameter_options(item, path))
        elif isinstance(item, (str, int, float, bool)) or item is None:
            rows.append((path, item))
    return rows


def _scalar_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if value is None:
        return "null"
    return "string"


def _review_id(path: Path, identity: str = "generic") -> str:
    return hashlib.sha256(f"{path.resolve()}::{identity}".encode("utf-8")).hexdigest()[:20]


def _candidate_by_id(root: Path, review_id: str) -> dict[str, Any]:
    if re.fullmatch(r"[a-f0-9]{20}", review_id) is None:
        raise ValueError("candidate review identity is invalid")
    matches = [item for item in _candidate_review_summaries(root) if item.get("review_id") == review_id]
    if len(matches) != 1:
        raise FileNotFoundError("candidate review item was not found")
    return matches[0]


def _lifecycle_candidate_summaries(root: Path) -> list[dict[str, Any]]:
    """Discover only current hash-valid candidates, retaining paths server-side."""

    from alphaquest.studio.candidate_review import CandidateReviewService, CandidateReviewV1

    layout = load_storage_layout(root)
    campaign_roots = tuple(path.resolve() for path in layout.campaign_roots)
    rows: list[dict[str, Any]] = []
    for evidence_root in layout.evidence_roots:
        resolved_evidence_root = evidence_root.resolve()
        for result_path in sorted(evidence_root.glob("**/reporting_v2/result_bundle_v2.json")):
            result_path = result_path.resolve()
            if not result_path.is_relative_to(resolved_evidence_root):
                continue
            initial = inspect_finalized_result(result_path)
            bundle = initial.get("bundle")
            manifest = initial.get("manifest")
            if (
                not initial.get("valid")
                or not isinstance(bundle, ResultBundleV2)
                or not isinstance(manifest, Mapping)
            ):
                continue
            source_config = str(manifest.get("source_config") or "").strip()
            if not source_config:
                continue
            config_path = resolve_recorded_path(source_config, project_root=root).resolve()
            if (
                config_path.name != "config.yaml"
                or not config_path.is_file()
                or not any(config_path.is_relative_to(base) for base in campaign_roots)
            ):
                continue
            context = resolve_campaign_context(config_path, project_root=root, layout=layout)
            if context is None or context.campaign_id != bundle.campaign_id:
                continue
            finalized = inspect_finalized_result(result_path, config_path=config_path)
            if not finalized.get("valid"):
                continue
            try:
                config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                continue
            if not isinstance(config, Mapping):
                continue
            attempt_id = str(config.get("attempt_id") or "original")
            instrument = str(config.get("symbol") or config.get("instrument") or "").strip()
            if re.fullmatch(r"[a-z0-9][a-z0-9_]*", attempt_id) is None or not instrument:
                continue
            try:
                attempts = FollowUpAttemptService(root).list_attempts(
                    bundle.campaign_id,
                    include_dataset_bindings=False,
                )
            except (OSError, ValueError, KeyError, FileNotFoundError):
                continue
            current_attempt = str((attempts[-1] if attempts else {}).get("attempt_id") or "")
            if current_attempt != attempt_id:
                continue
            for review_path in sorted(result_path.parent.glob("candidate_review*.json")):
                if review_path.is_symlink() or not review_path.resolve().is_relative_to(
                    resolved_evidence_root
                ):
                    continue
                review_report = CandidateReviewService().inspect(
                    candidate_review_path=review_path,
                    result_bundle_path=result_path,
                    config_path=config_path,
                )
                review = review_report.get("review")
                if (
                    not review_report.get("valid")
                    or review_report.get("lifecycle_state") != "candidate"
                    or not isinstance(review, CandidateReviewV1)
                    or review.decision != "approved_candidate"
                    or (review.campaign_id, review.variant_id, review.run_id)
                    != (bundle.campaign_id, bundle.variant_id, bundle.run_id)
                ):
                    continue
                result_hash = hashlib.sha256(result_path.read_bytes()).hexdigest()
                review_hash = hashlib.sha256(review_path.read_bytes()).hexdigest()
                config_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
                candidate_id = hashlib.sha256(
                    json.dumps(
                        {
                            "campaign_id": bundle.campaign_id,
                            "variant_id": bundle.variant_id,
                            "attempt_id": attempt_id,
                            "run_id": bundle.run_id,
                            "result_bundle_sha256": result_hash,
                            "candidate_review_sha256": review_hash,
                            "config_sha256": config_hash,
                            "eligibility_basis": review.eligibility_basis,
                            "account_assessment_id": review.account_assessment_id,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest()
                rows.append(
                    {
                        "candidate_id": candidate_id,
                        "campaign_id": bundle.campaign_id,
                        "variant_id": bundle.variant_id,
                        "attempt_id": attempt_id,
                        "run_id": bundle.run_id,
                        "instrument": instrument,
                        "eligibility_basis": review.eligibility_basis,
                        "account_assessment_id": review.account_assessment_id,
                        "account_profile_id": review.account_profile_id,
                        "account_profile_version": review.account_profile_version,
                        "result_bundle_sha256": result_hash,
                        "candidate_review_sha256": review_hash,
                        "config_sha256": config_hash,
                        "candidate_reviewed_at": review.reviewed_at.isoformat(),
                        "_result_bundle_path": str(result_path),
                        "_candidate_review_path": str(review_path.resolve()),
                        "_config_path": str(config_path),
                    }
                )
    scope_counts: dict[tuple[str, str, str], int] = {}
    for item in rows:
        scope = (
            str(item["campaign_id"]),
            str(item["variant_id"]),
            str(item["attempt_id"]),
        )
        scope_counts[scope] = scope_counts.get(scope, 0) + 1
    rows = [
        item
        for item in rows
        if scope_counts[
            (
                str(item["campaign_id"]),
                str(item["variant_id"]),
                str(item["attempt_id"]),
            )
        ]
        == 1
    ]
    rows.sort(
        key=lambda item: (
            str(item["campaign_id"]),
            str(item["variant_id"]),
            str(item["attempt_id"]),
            str(item["run_id"]),
        )
    )
    return rows


def _public_lifecycle_candidate(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if not str(key).startswith("_")}


def _lifecycle_candidate_by_id(root: Path, candidate_id: str) -> dict[str, Any]:
    if re.fullmatch(r"[a-f0-9]{64}", candidate_id) is None:
        raise ValueError("lifecycle candidate identity is invalid")
    matches = [
        item
        for item in _lifecycle_candidate_summaries(root)
        if item.get("candidate_id") == candidate_id
    ]
    if len(matches) != 1:
        raise FileNotFoundError("current lifecycle candidate was not found")
    return matches[0]


def _portfolio_review_path(root: Path, review_id: str) -> Path:
    if re.fullmatch(r"[a-f0-9]{64}", review_id) is None:
        raise ValueError("portfolio review identity is invalid")
    directory = load_storage_layout(root).research_artifact_root / "portfolio_reviews"
    path = (directory / f"portfolio_review_{review_id}.json").resolve()
    if path.parent != directory.resolve() or not path.is_file():
        raise FileNotFoundError("portfolio review was not found")
    return path


def _deployment_decision_path(root: Path, decision_id: str) -> Path:
    if re.fullmatch(r"[a-f0-9]{64}", decision_id) is None:
        raise ValueError("deployment decision identity is invalid")
    directory = load_storage_layout(root).research_artifact_root / "deployment_decisions"
    path = (directory / f"deployment_decision_{decision_id}.json").resolve()
    if path.parent != directory.resolve() or not path.is_file():
        raise FileNotFoundError("deployment decision was not found")
    return path


def _public_portfolio_report(
    report: Mapping[str, Any],
    *,
    fallback_review: PortfolioReviewV1 | None = None,
) -> dict[str, Any]:
    review = report.get("review")
    if not isinstance(review, PortfolioReviewV1):
        review = fallback_review
    payload = review.model_dump(mode="json", by_alias=True) if review is not None else {}
    if isinstance(payload.get("candidates"), list):
        payload["candidates"] = [
            {key: item for key, item in candidate.items() if not key.endswith("_path")}
            for candidate in payload["candidates"]
            if isinstance(candidate, dict)
        ]
    return {
        **payload,
        "valid": bool(report.get("valid")),
        "errors": list(report.get("errors") or []),
        "review_sha256": report.get("review_sha256"),
        "automatic_deployment_permitted": False,
    }


def _public_deployment_report(
    report: Mapping[str, Any],
    *,
    fallback_decision: DeploymentDecisionV1 | None = None,
) -> dict[str, Any]:
    decision = report.get("decision")
    if not isinstance(decision, DeploymentDecisionV1):
        decision = fallback_decision
    payload = decision.model_dump(mode="json", by_alias=True) if decision is not None else {}
    payload.pop("portfolio_review_path", None)
    candidates = payload.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            source = candidate.get("candidate")
            if isinstance(source, dict):
                candidate["candidate"] = {
                    key: item for key, item in source.items() if not key.endswith("_path")
                }
            forward = candidate.get("forward_incubation")
            if isinstance(forward, dict):
                candidate["forward_incubation"] = {
                    key: item for key, item in forward.items() if not key.endswith("_path")
                }
    return {
        **payload,
        "valid": bool(report.get("valid")),
        "errors": list(report.get("errors") or []),
        "decision_sha256": report.get("decision_sha256"),
        "order_submission_permitted": False,
        "automatic_retirement_permitted": False,
        "execution_capability": "none",
    }


def _public_monitoring_detail(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(value)
    events = payload.get("events")
    if isinstance(events, list):
        payload["events"] = [
            {key: item for key, item in event.items() if key != "source_trade_log_path"}
            for event in events
            if isinstance(event, dict)
        ]
    payload["order_submission_permitted"] = False
    payload["automatic_retirement_permitted"] = False
    return payload


_UPLOAD_TOKEN = re.compile(r"^[a-f0-9]{32}$")
_CANONICAL_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")


def _resolve_upload(root: Path, token: str) -> Path:
    if _UPLOAD_TOKEN.fullmatch(token) is None:
        raise ValueError("upload token is invalid")
    directory = load_storage_layout(root).studio_runtime_root / "raw-attachments" / token
    files = [path for path in directory.iterdir()] if directory.is_dir() else []
    if len(files) != 1 or not files[0].is_file():
        raise FileNotFoundError("uploaded attachment is unavailable or ambiguous")
    return files[0]


def _guess_column(columns: list[str], canonical: str) -> str | None:
    aliases = {
        "timestamp": ("timestamp", "time", "datetime", "date"),
        "open": ("open", "o"),
        "high": ("high", "h"),
        "low": ("low", "l"),
        "close": ("close", "c"),
        "volume": ("volume", "vol", "v"),
    }[canonical]
    lowered = [item.casefold() for item in columns]
    for alias in aliases:
        if alias in lowered:
            return columns[lowered.index(alias)]
    return columns[0] if columns else None


__all__ = ["register_api_routes"]
