"""FastAPI contract for the local AlphaQuest Research Studio.

This module contains transport concerns only.  It delegates every mutation to
the existing governed services so the React client cannot bypass publication,
approval, lineage, or one-run-per-attempt controls.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Literal, Mapping
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError as PydanticValidationError
import yaml

from alphaquest.authoring.catalog import get_certified_module_catalog
from alphaquest.authoring.models import EconomicEdgeFingerprintV1, ExecutionSettingsV1, ResearchSourceV1
from alphaquest.prop.profiles import list_prop_profiles
from alphaquest.research.storage import (
    load_storage_layout,
    resolve_campaign_context,
    resolve_recorded_path,
)
from alphaquest.studio.data_import import DataImportSpec, DatasetImporter
from alphaquest.studio.finalization import inspect_finalized_result
from alphaquest.studio.followups import FollowUpAttemptRequestV1, FollowUpAttemptService
from alphaquest.studio.jobs import OperationalState, SQLiteJobQueue
from alphaquest.studio.results import RESULT_BUNDLE_FILENAME, ResultBundleV2
from alphaquest.studio.settings import StudioSettings, load_settings, save_settings
from alphaquest.studio.workflow import StudioWorkflowService
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


class BriefRequest(APIModel):
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


class CandidateDecisionRequest(APIModel):
    review_id: str
    evidence_token: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewer: str
    decision: Literal["approved_candidate", "rejected", "needs_manual_review"]
    notes: str


class AIDraftRequest(APIModel):
    campaign_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_]*$")
    selected_text: str = Field(min_length=1)
    source_title: str = Field(min_length=1)
    instrument: Literal["ES", "NQ"]


class APIKeyRequest(APIModel):
    api_key: str = Field(min_length=1)


class PDFExtractRequest(APIModel):
    upload_token: str = Field(pattern=r"^[a-f0-9]{32}$")
    page_indexes: list[int] = Field(min_length=1, max_length=500)


def register_api_routes(app: FastAPI, project_root: str | Path) -> None:
    """Register the versioned local JSON contract on ``app``."""

    root = Path(project_root).resolve()
    workflow = StudioWorkflowService(root)

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
        reviews = [*mechanics_reviews, *candidate_reviews, *indexed_reviews]
        jobs = _jobs(root, limit=30)
        datasets = list_dataset_manifests(root)
        modules = _modules(root)
        settings = load_settings(project_root=root).model_dump(mode="json")
        active = sum(item.get("lifecycle") == "active" for item in campaigns)
        attention = [
            item
            for item in jobs
            if item["operational_state"] in {"BLOCKED", "FAILED_OPERATIONAL"}
            or item.get("research_verdict") == "NEEDS MANUAL REVIEW"
        ]
        attention.extend(
            item
            for item in reviews
            if item.get("type") in {"mechanics", "candidate"}
            or item.get("verdict") in {"NEEDS MANUAL REVIEW", "NEEDS_MANUAL_REVIEW"}
        )
        return {
            "workspace": {
                "name": root.name,
                "path": str(root),
                "ui_runtime": "react-fastapi",
                "candidate_only": True,
                "index_refresh": refresh,
                "metrics": {
                    "live_drafts": len(drafts),
                    "active_campaigns": active,
                    "review_items": len(reviews),
                    "certified_modules": len(modules),
                },
            },
            "drafts": drafts,
            "campaigns": campaigns,
            "reviews": reviews,
            "jobs": jobs,
            "attention": attention,
            "libraries": {
                "datasets": datasets,
                "modules": modules,
                "prop_profiles": list_prop_profiles(),
            },
            "settings": settings,
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
        columns = DatasetImporter(root).inspect_columns(destination)
        return {
            "upload_token": token,
            "filename": safe_name,
            "size_bytes": size,
            "columns": columns,
            "suggested_mapping": {name: _guess_column(columns, name) for name in _CANONICAL_COLUMNS},
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
    def campaign(campaign_id: str) -> dict[str, Any]:
        campaigns = {str(item["campaign_id"]): item for item in list_published_campaigns(root)}
        if campaign_id not in campaigns:
            raise FileNotFoundError(f"published campaign not found: {campaign_id}")
        service = FollowUpAttemptService(root)
        attempts = service.list_attempts(campaign_id) if campaigns[campaign_id].get("studio_managed") else []
        mechanics_approval = (
            _attempt_mechanics_gate(root, campaign_id, attempts)
            if campaigns[campaign_id].get("studio_managed")
            else {}
        )
        rows, latest = _authoritative_results(root, campaign_id)
        next_variant: dict[str, Any]
        try:
            from alphaquest.studio.sequential_variants import SequentialVariantService

            next_variant = SequentialVariantService(root).eligibility(campaign_id)
        except Exception as exc:
            next_variant = {"eligible": False, "blockers": [str(exc)]}
        return {
            "campaign": campaigns[campaign_id],
            "attempts": attempts,
            "mechanics_approval": mechanics_approval,
            "stage_matrix": rows,
            "latest_results": latest,
            "recommended_action": _campaign_next_action(campaigns[campaign_id], rows),
            "next_variant": next_variant,
        }

    @app.get("/api/campaigns/{campaign_id}/next-variant")
    def next_variant(campaign_id: str) -> dict[str, Any]:
        from alphaquest.studio.sequential_variants import SequentialVariantService

        return SequentialVariantService(root).suggestion(campaign_id)

    @app.post("/api/campaigns/{campaign_id}/next-variant", status_code=201)
    def append_next_variant(campaign_id: str, value: NextVariantRequest) -> dict[str, Any]:
        from alphaquest.studio.sequential_variants import SequentialVariantService

        return SequentialVariantService(root).append(
            campaign_id,
            variant=value.variant,
            failure_analysis=value.failure_analysis,
            created_by=value.created_by,
        )

    @app.get("/api/campaigns/{campaign_id}/follow-up-options")
    def follow_up_options(campaign_id: str, parent_attempt_id: str = "original") -> dict[str, Any]:
        return _follow_up_options(root, campaign_id, parent_attempt_id)

    @app.post("/api/campaigns/{campaign_id}/follow-ups", status_code=201)
    def create_follow_up(campaign_id: str, value: FollowUpAttemptRequestV1) -> dict[str, Any]:
        if value.campaign_id != campaign_id:
            raise ValueError("follow-up campaign identity does not match the selected campaign")
        result = FollowUpAttemptService(root).create(value)
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
        return {"jobs": [_job_payload(job) for job in jobs]}

    @app.post("/api/campaigns/{campaign_id}/queue-run")
    def queue_run(campaign_id: str, value: AttemptRequest) -> dict[str, Any]:
        jobs = FollowUpAttemptService(root).queue_performance(campaign_id, value.attempt_id)
        return {"jobs": [_job_payload(job) for job in jobs]}

    @app.get("/api/reviews")
    def reviews() -> dict[str, Any]:
        return {
            "items": list_review_queue(root),
            "mechanics": _mechanics_review_summaries(root),
            "candidate": _candidate_review_summaries(root),
        }

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

    @app.get("/api/libraries")
    def libraries() -> dict[str, Any]:
        return {
            "datasets": list_dataset_manifests(root),
            "modules": _modules(root),
            "prop_profiles": list_prop_profiles(),
        }

    @app.get("/api/jobs")
    def jobs(limit: int = 100) -> dict[str, Any]:
        return {"jobs": _jobs(root, limit=max(1, min(500, limit)))}

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict[str, Any]:
        database = load_storage_layout(root).studio_runtime_root / "jobs.sqlite3"
        if not database.is_file():
            raise FileNotFoundError("Studio job queue does not exist")
        return _job_payload(SQLiteJobQueue(database).request_cancel(job_id))

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
    from alphaquest.strategy_certification import load_strategy_certifications

    certifications = load_strategy_certifications(project_root, require_current=False)
    result = []
    for item in get_certified_module_catalog().all():
        record = item.model_dump(mode="json", by_alias=True)
        certification = certifications.get(item.name) if item.module_type == "entry" else None
        if certification is not None:
            record.update(
                {
                    "certification_status": certification.certification_status,
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
                }
            )
        result.append(record)
    return result


def _compact_review(value: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "review_id",
        "campaign_id",
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
        eta_seconds = phase_elapsed / progress.completed * (progress.total - progress.completed)
    return {
        **progress.model_dump(mode="json", by_alias=True),
        "elapsed_seconds": elapsed_seconds,
        "eta_seconds": eta_seconds,
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
        presented[str(variant_id)] = payload
        row = row_by_variant.get(str(variant_id))
        if row is None:
            continue
        row.update(
            {
                "research verdict": payload["research_verdict"],
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
    return {
        **payload,
        "research_verdict": bundle.verdict,
        "first_failed_or_unresolved_gate": _first_unresolved_bundle_gate(bundle),
        "finalization": {"valid": True, "errors": []},
        "source_index_verdict": entry.get("research_verdict"),
        "artifact_previews": _result_artifact_previews(bundle, bundle_path),
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


def _attempt_mechanics_gate(
    root: Path,
    campaign_id: str,
    attempts: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    from alphaquest.studio.approvals import MechanicsApprovalService

    follow_ups = FollowUpAttemptService(root)
    approvals = MechanicsApprovalService()
    result: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        attempt_id = str(attempt.get("attempt_id") or "")
        variants: list[dict[str, Any]] = []
        try:
            paths = follow_ups.config_paths(campaign_id, attempt_id)
            for path in paths:
                try:
                    report = approvals.inspect(path)
                    status = str(report.get("status") or "NEEDS_REVIEW")
                    errors = [str(item) for item in report.get("errors") or []]
                except Exception as exc:
                    status = "NEEDS_MANUAL_REVIEW"
                    errors = [str(exc)]
                variants.append(
                    {
                        "variant_id": path.parent.name,
                        "status": status,
                        "errors": errors,
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
                else "Every currently declared variant requires current mechanics approval before performance testing."
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
        for attempt in service.list_attempts(
            campaign_id,
            include_dataset_bindings=False,
        ):
            attempt_id = str(attempt["attempt_id"])
            for path in service.config_paths(campaign_id, attempt_id):
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
                        "attempt_id": attempt_id,
                        "variant_id": path.parent.name,
                    }
                )
                summaries.append(payload)
    return summaries


def _candidate_review_summaries(root: Path) -> list[dict[str, Any]]:
    from alphaquest.studio.candidate_review import CANDIDATE_REVIEW_FILENAME, CandidateReviewService

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
            if not valid or presentation.get("research_verdict") != "PASS":
                continue

            review_path = path.parent / CANDIDATE_REVIEW_FILENAME
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
                    # Any valid independent terminal decision (approved,
                    # rejected, or manual-review) closes this queue item.
                    continue
                review_status = "invalid_or_stale"
                review_blockers = [
                    "Existing candidate review is invalid or stale: " + str(error)
                    for error in review_report.get("errors") or ["verification did not pass"]
                ]
            rows.append(
                {
                    "review_id": _review_id(path),
                    "path": str(path),
                    "valid": valid,
                    "campaign_id": campaign_id,
                    "variant_id": variant_id,
                    "run_id": presentation.get("run_id") or run_id or None,
                    "verdict": presentation["research_verdict"],
                    "verdict_message": presentation["verdict_message"],
                    "errors": review_blockers,
                    "review_status": review_status,
                    "review_valid": False,
                    "review_blockers": review_blockers,
                    "evidence_token": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "candidate_review_path": str(review_path) if review_path.is_file() else None,
                    "metrics": presentation.get("metrics") or {},
                    "stage_criteria": presentation.get("stage_criteria") or [],
                    "breakdowns": presentation.get("breakdowns"),
                    "supplemental_artifacts": presentation.get("supplemental_artifacts"),
                    "result_bundle": presentation,
                }
            )
    return rows


def _attempt_config(root: Path, campaign_id: str, attempt_id: str, variant_id: str) -> Path:
    paths = FollowUpAttemptService(root).config_paths(campaign_id, attempt_id)
    matches = [path for path in paths if path.parent.name == variant_id]
    if len(matches) != 1:
        raise FileNotFoundError("governed mechanics-review variant was not found")
    return matches[0]


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

    service = FollowUpAttemptService(root)
    attempts = service.list_attempts(campaign_id)
    if parent_attempt_id not in {str(item.get("attempt_id")) for item in attempts}:
        raise FileNotFoundError("selected parent attempt was not found")
    parameters: dict[str, list[dict[str, Any]]] = {}
    event_parameter_declarations: dict[str, list[dict[str, Any]]] = {}
    for path in service.config_paths(campaign_id, parent_attempt_id):
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
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
            from alphaquest.strategy_certification import get_strategy_certification

            certification = get_strategy_certification(
                str(event.get("module") or ""), root, require_current=True
            )
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
    return {
        "attempt_kinds": [
            {"value": "replication", "label": "Exact replication"},
            {"value": "data_refresh", "label": "Governed data refresh"},
            {"value": "methodology_rerun", "label": "Methodology rerun"},
            {"value": "pre_pnl_mechanics_correction", "label": "Pre-PnL mechanics correction"},
            {"value": "pre_pnl_parameter_declaration", "label": "Pre-PnL parameter declaration"},
            {"value": "rescue", "label": "Authorized rescue"},
        ],
        "parent_attempt_id": parent_attempt_id,
        "parameters": parameters,
        "event_parameter_declarations": event_parameter_declarations,
        "datasets": datasets,
        "rescue_allowed": bool((campaign.get("rescue_policy") or {}).get("allowed")),
        "reason_min_length": 80,
    }


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


def _review_id(path: Path) -> str:
    return hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:20]


def _candidate_by_id(root: Path, review_id: str) -> dict[str, Any]:
    if re.fullmatch(r"[a-f0-9]{20}", review_id) is None:
        raise ValueError("candidate review identity is invalid")
    matches = [item for item in _candidate_review_summaries(root) if item.get("review_id") == review_id]
    if len(matches) != 1:
        raise FileNotFoundError("candidate review item was not found")
    return matches[0]


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
