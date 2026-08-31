"""Immutable, hash-bound forward/paper incubation for candidate strategies.

Forward incubation is deliberately separate from historical campaign stages.
It starts only after an independent candidate approval and can make a candidate
eligible for another human review; it can never promote a strategy by itself.
"""

from __future__ import annotations

from datetime import UTC, datetime
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import yaml

from alphaquest.authoring.models import ResearchObjectivesV1
from alphaquest.research.storage import load_storage_layout, resolve_recorded_path
from alphaquest.studio.candidate_review import CandidateReviewService, CandidateReviewV1
from alphaquest.studio.results import RESULT_BUNDLE_FILENAME


FORWARD_INCUBATION_PLAN_SCHEMA = "alphaquest.forward-incubation-plan/v1"
FORWARD_INCUBATION_EVENT_SCHEMA = "alphaquest.forward-incubation-event/v1"
FORWARD_INCUBATION_EVENT_HEAD_SCHEMA = "alphaquest.forward-incubation-event-head/v1"
FORWARD_INCUBATION_DIRECTORY = "forward_incubation"
PLAN_FILENAME = "plan.json"
PLAN_RECEIPT_FILENAME = "plan.sha256"
EVENTS_FILENAME = "events.jsonl"
EVENT_HEAD_FILENAME = "events.head.json"
EVIDENCE_DIRECTORY = "evidence"
MINIMUM_CALENDAR_DAYS = 90
MINIMUM_TRADES = 30

ForwardIncubationStatus = Literal[
    "ACTIVE",
    "ELIGIBLE_FOR_REVIEW",
    "FAILED",
    "RETIRED",
    "NEEDS MANUAL REVIEW",
]

_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_]*$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ForwardIncubationThresholdsV1(_StrictModel):
    minimum_calendar_days: int = Field(ge=MINIMUM_CALENDAR_DAYS, le=1095)
    minimum_trades: int = Field(ge=MINIMUM_TRADES)
    abandonment_rules: list[str] = Field(min_length=1)
    retirement_rules: list[str] = Field(min_length=1)

    @field_validator("abandonment_rules", "retirement_rules")
    @classmethod
    def _nonblank_rules(cls, values: list[str]) -> list[str]:
        cleaned = [str(value).strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("incubation rules must be non-empty")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("incubation rules must be unique")
        return cleaned


class ForwardIncubationPlanV1(_StrictModel):
    """Frozen source identity and minimum duration/sample contract."""

    schema_name: Literal["alphaquest.forward-incubation-plan/v1"] = Field(
        default=FORWARD_INCUBATION_PLAN_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    campaign_id: str
    variant_id: str
    attempt_id: str
    run_id: str
    started_at: datetime
    created_by: str
    thresholds: ForwardIncubationThresholdsV1
    candidate_review_path: str
    result_bundle_path: str
    config_path: str
    candidate_review_sha256: str
    result_bundle_sha256: str
    config_sha256: str
    governed_config_hash: str
    research_objectives_sha256: str

    @field_validator("campaign_id", "variant_id", "attempt_id")
    @classmethod
    def _identifier(cls, value: str) -> str:
        return _validated_identifier(value)

    @field_validator(
        "run_id",
        "created_by",
        "candidate_review_path",
        "result_bundle_path",
        "config_path",
        "governed_config_hash",
    )
    @classmethod
    def _nonblank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must be non-empty")
        return cleaned

    @field_validator(
        "candidate_review_sha256",
        "result_bundle_sha256",
        "config_sha256",
        "research_objectives_sha256",
    )
    @classmethod
    def _sha256(cls, value: str) -> str:
        return _validated_sha256(value)

    @field_validator("started_at")
    @classmethod
    def _aware_start(cls, value: datetime) -> datetime:
        return _aware_datetime(value, "started_at")


class ForwardIncubationEventV1(_StrictModel):
    """One append-only event in the incubation hash chain."""

    schema_name: Literal["alphaquest.forward-incubation-event/v1"] = Field(
        default=FORWARD_INCUBATION_EVENT_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    sequence: int = Field(ge=1)
    event_type: Literal["observation", "review", "retirement"]
    occurred_at: datetime
    actor: str
    notes: str
    plan_sha256: str
    previous_event_sha256: str
    event_sha256: str
    evidence_sha256: str | None = None
    evidence_path: str | None = None
    trade_count_delta: int | None = Field(default=None, ge=0)
    net_pnl_delta: float | None = None
    prop_rule_breach: bool | None = None
    forced_flatten_violation: bool | None = None
    triggered_abandonment_rules: list[str] = Field(default_factory=list)
    review_decision: Literal["continue", "fail", "needs_manual_review"] | None = None
    retirement_reason: str | None = None

    @field_validator("occurred_at")
    @classmethod
    def _aware_event(cls, value: datetime) -> datetime:
        return _aware_datetime(value, "occurred_at")

    @field_validator("actor", "notes")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("actor and notes must be non-empty")
        return cleaned

    @field_validator("plan_sha256", "previous_event_sha256", "event_sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        return _validated_sha256(value)

    @field_validator("evidence_sha256")
    @classmethod
    def _optional_sha256(cls, value: str | None) -> str | None:
        return _validated_sha256(value) if value is not None else None

    @field_validator("evidence_path")
    @classmethod
    def _optional_evidence_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if re.fullmatch(r"evidence/[a-f0-9]{64}(?:\.[a-z0-9]{1,10})?", cleaned) is None:
            raise ValueError("evidence_path must identify a content-addressed incubation attachment")
        return cleaned

    @field_validator("net_pnl_delta")
    @classmethod
    def _finite_pnl(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("net_pnl_delta must be finite")
        return value

    @model_validator(mode="after")
    def _event_shape(self) -> "ForwardIncubationEventV1":
        if self.evidence_path is not None and self.evidence_sha256 is not None:
            recorded_digest = Path(self.evidence_path).name.split(".", 1)[0]
            if recorded_digest != self.evidence_sha256:
                raise ValueError("evidence path and SHA-256 identity do not match")
        if self.event_type == "observation":
            if self.evidence_sha256 is None or self.evidence_path is None:
                raise ValueError("observations require a durable content-addressed evidence attachment")
            if self.trade_count_delta is None or self.net_pnl_delta is None:
                raise ValueError("observations require trade-count and net-PnL deltas")
            if self.prop_rule_breach is None or self.forced_flatten_violation is None:
                raise ValueError("observations require explicit prop and forced-flatten outcomes")
            if self.review_decision is not None or self.retirement_reason is not None:
                raise ValueError("observation contains review-only fields")
        elif self.event_type == "review":
            if self.evidence_sha256 is None or self.evidence_path is None or self.review_decision is None:
                raise ValueError("reviews require durable evidence and an explicit decision")
            if any(
                value is not None
                for value in (
                    self.trade_count_delta,
                    self.net_pnl_delta,
                    self.prop_rule_breach,
                    self.forced_flatten_violation,
                    self.retirement_reason,
                )
            ) or self.triggered_abandonment_rules:
                raise ValueError("review contains observation- or retirement-only fields")
        else:
            if not str(self.retirement_reason or "").strip():
                raise ValueError("retirement requires a reason")
            if any(
                value is not None
                for value in (
                    self.evidence_sha256,
                    self.evidence_path,
                    self.trade_count_delta,
                    self.net_pnl_delta,
                    self.prop_rule_breach,
                    self.forced_flatten_violation,
                    self.review_decision,
                )
            ) or self.triggered_abandonment_rules:
                raise ValueError("retirement contains observation- or review-only fields")
        return self


class ForwardIncubationService:
    """Create and inspect immutable true-forward incubation records."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.layout = load_storage_layout(self.project_root)
        self.root = self.layout.research_artifact_root / FORWARD_INCUBATION_DIRECTORY
        self._clock = clock or (lambda: datetime.now(UTC))

    def start(
        self,
        *,
        campaign_id: str,
        variant_id: str,
        attempt_id: str,
        created_by: str,
    ) -> dict[str, Any]:
        """Start from the sole current, hash-valid approved candidate record."""

        campaign = _validated_identifier(campaign_id)
        variant = _validated_identifier(variant_id)
        attempt = _validated_identifier(attempt_id)
        target = self._record_dir(campaign, variant, attempt)
        if target.exists():
            raise FileExistsError("forward incubation already exists for this campaign/variant/attempt")
        sources = self._find_current_candidate(campaign, variant, attempt)
        return self.start_from_paths(
            candidate_review_path=sources[0],
            result_bundle_path=sources[1],
            config_path=sources[2],
            expected_campaign_id=campaign,
            expected_variant_id=variant,
            expected_attempt_id=attempt,
            created_by=created_by,
        )

    def start_from_paths(
        self,
        *,
        candidate_review_path: str | Path,
        result_bundle_path: str | Path,
        config_path: str | Path,
        expected_campaign_id: str,
        expected_variant_id: str,
        expected_attempt_id: str,
        created_by: str,
    ) -> dict[str, Any]:
        """Validated implementation hook used after governed source discovery."""

        campaign = _validated_identifier(expected_campaign_id)
        variant = _validated_identifier(expected_variant_id)
        attempt = _validated_identifier(expected_attempt_id)
        actor = created_by.strip()
        if not actor:
            raise ValueError("created_by is required")
        target = self._record_dir(campaign, variant, attempt)
        if target.exists():
            raise FileExistsError("forward incubation already exists for this campaign/variant/attempt")

        review_path = Path(candidate_review_path).resolve()
        result_path = Path(result_bundle_path).resolve()
        config = Path(config_path).resolve()
        report = CandidateReviewService().inspect(
            candidate_review_path=review_path,
            result_bundle_path=result_path,
            config_path=config,
        )
        if not report.get("valid"):
            raise ValueError(
                "forward incubation requires a current hash-valid candidate review: "
                + "; ".join(str(item) for item in report.get("errors") or ["verification failed"])
            )
        review = report.get("review")
        if not isinstance(review, CandidateReviewV1):
            raise ValueError("candidate-review verification did not return the frozen review")
        if review.decision != "approved_candidate" or review.lifecycle_state != "candidate":
            raise ValueError("forward incubation requires an approved candidate-review decision")
        if (review.campaign_id, review.variant_id) != (campaign, variant):
            raise ValueError("candidate-review identity does not match the requested incubation")

        cfg = _load_yaml(config)
        config_identity = (
            str(cfg.get("campaign_id") or ""),
            str(cfg.get("variant_id") or config.parent.name),
            str(cfg.get("attempt_id") or "original"),
        )
        if config_identity != (campaign, variant, attempt):
            raise ValueError("config campaign/variant/attempt identity does not match the requested incubation")
        objectives, objectives_sha256 = _validated_objectives(cfg)
        started_at = _aware_datetime(self._clock(), "started_at")
        if started_at < review.reviewed_at:
            raise ValueError("system time precedes the frozen candidate-review timestamp")

        plan = ForwardIncubationPlanV1(
            campaign_id=campaign,
            variant_id=variant,
            attempt_id=attempt,
            run_id=review.run_id,
            started_at=started_at,
            created_by=actor,
            thresholds=_thresholds_from_objectives(objectives),
            candidate_review_path=_recorded_path(review_path, self.project_root),
            result_bundle_path=_recorded_path(result_path, self.project_root),
            config_path=_recorded_path(config, self.project_root),
            candidate_review_sha256=_file_sha256(review_path),
            result_bundle_sha256=_file_sha256(result_path),
            config_sha256=_file_sha256(config),
            governed_config_hash=review.config_hash,
            research_objectives_sha256=objectives_sha256,
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.mkdir()
        plan_bytes = _json_bytes(plan.model_dump(mode="json", by_alias=True), pretty=True)
        _write_exclusive(target / PLAN_FILENAME, plan_bytes)
        plan_sha256 = _sha256_bytes(plan_bytes)
        _write_exclusive(target / PLAN_RECEIPT_FILENAME, (plan_sha256 + "\n").encode("ascii"))
        _write_exclusive(target / EVENTS_FILENAME, b"")
        _write_exclusive(
            target / EVENT_HEAD_FILENAME,
            _json_bytes(_event_head_payload(0, plan_sha256, _sha256_bytes(b"")), pretty=True),
        )
        return self.detail(campaign, variant, attempt)

    def import_evidence_attachment(
        self,
        campaign_id: str,
        variant_id: str,
        attempt_id: str,
        source_path: str | Path,
    ) -> dict[str, str | int]:
        """Copy a runtime upload into immutable content-addressed storage."""

        directory = self._record_dir(
            _validated_identifier(campaign_id),
            _validated_identifier(variant_id),
            _validated_identifier(attempt_id),
        )
        if not (directory / PLAN_FILENAME).is_file():
            raise FileNotFoundError("forward incubation was not found")
        current = self.detail(campaign_id, variant_id, attempt_id)
        if current["errors"]:
            raise RuntimeError("cannot import evidence into a hash-drifted or invalid incubation record")
        if current["status"] in {"FAILED", "RETIRED"}:
            raise RuntimeError(f"cannot import evidence into a terminal incubation with status {current['status']}")
        source = Path(source_path).resolve()
        if not source.is_file():
            raise FileNotFoundError("incubation evidence attachment was not found")
        evidence_dir = directory / EVIDENCE_DIRECTORY
        evidence_dir.mkdir(parents=True, exist_ok=True)
        if evidence_dir.is_symlink() or not evidence_dir.is_dir():
            raise RuntimeError("incubation evidence directory is not a regular governed directory")
        suffix = source.suffix.casefold()
        if re.fullmatch(r"\.[a-z0-9]{1,10}", suffix) is None:
            suffix = ".bin"
        digest = hashlib.sha256()
        size = 0
        with NamedTemporaryFile(
            dir=evidence_dir,
            prefix=".evidence.",
            suffix=".tmp",
            delete=False,
        ) as handle, source.open("rb") as input_handle:
            temporary = Path(handle.name)
            for chunk in iter(lambda: input_handle.read(1024 * 1024), b""):
                size += len(chunk)
                digest.update(chunk)
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        if size == 0:
            temporary.unlink(missing_ok=True)
            raise ValueError("incubation evidence attachment must not be empty")
        sha256 = digest.hexdigest()
        target = evidence_dir / f"{sha256}{suffix}"
        try:
            if target.exists():
                if target.is_symlink() or not target.is_file() or _file_sha256(target) != sha256:
                    raise RuntimeError("content-addressed incubation evidence target is invalid")
            else:
                os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return {
            "evidence_path": target.relative_to(directory).as_posix(),
            "evidence_sha256": sha256,
            "size_bytes": size,
        }

    def append_observation(
        self,
        campaign_id: str,
        variant_id: str,
        attempt_id: str,
        *,
        recorded_by: str,
        notes: str,
        evidence_source_path: str | Path,
        trade_count_delta: int,
        net_pnl_delta: float,
        prop_rule_breach: bool,
        forced_flatten_violation: bool,
        triggered_abandonment_rules: list[str] | None = None,
    ) -> dict[str, Any]:
        current = self.detail(campaign_id, variant_id, attempt_id)
        if current["errors"]:
            raise RuntimeError("cannot append to a hash-drifted or invalid incubation record")
        if current["status"] not in {"ACTIVE", "ELIGIBLE_FOR_REVIEW"}:
            raise RuntimeError(f"cannot append an observation while incubation status is {current['status']}")
        plan = ForwardIncubationPlanV1.model_validate(current["plan"])
        rules = [str(value).strip() for value in (triggered_abandonment_rules or [])]
        unknown = sorted(set(rules) - set(plan.thresholds.abandonment_rules))
        if unknown:
            raise ValueError("observation cites undeclared abandonment rules: " + ", ".join(unknown))
        evidence = self.import_evidence_attachment(
            campaign_id,
            variant_id,
            attempt_id,
            evidence_source_path,
        )
        self._append_event(
            plan,
            {
                "event_type": "observation",
                "actor": recorded_by,
                "notes": notes,
                "evidence_sha256": evidence["evidence_sha256"],
                "evidence_path": evidence["evidence_path"],
                "trade_count_delta": trade_count_delta,
                "net_pnl_delta": net_pnl_delta,
                "prop_rule_breach": prop_rule_breach,
                "forced_flatten_violation": forced_flatten_violation,
                "triggered_abandonment_rules": rules,
            },
        )
        return self.detail(campaign_id, variant_id, attempt_id)

    def append_review(
        self,
        campaign_id: str,
        variant_id: str,
        attempt_id: str,
        *,
        reviewer: str,
        notes: str,
        evidence_source_path: str | Path,
        decision: Literal["continue", "fail", "needs_manual_review"],
    ) -> dict[str, Any]:
        current = self.detail(campaign_id, variant_id, attempt_id)
        if current["errors"]:
            raise RuntimeError("cannot append to a hash-drifted or invalid incubation record")
        if current["status"] in {"FAILED", "RETIRED"}:
            raise RuntimeError(f"cannot review a terminal incubation with status {current['status']}")
        plan = ForwardIncubationPlanV1.model_validate(current["plan"])
        evidence = self.import_evidence_attachment(
            campaign_id,
            variant_id,
            attempt_id,
            evidence_source_path,
        )
        self._append_event(
            plan,
            {
                "event_type": "review",
                "actor": reviewer,
                "notes": notes,
                "evidence_sha256": evidence["evidence_sha256"],
                "evidence_path": evidence["evidence_path"],
                "review_decision": decision,
            },
        )
        return self.detail(campaign_id, variant_id, attempt_id)

    def retire(
        self,
        campaign_id: str,
        variant_id: str,
        attempt_id: str,
        *,
        retired_by: str,
        reason: str,
    ) -> dict[str, Any]:
        current = self.detail(campaign_id, variant_id, attempt_id)
        if current["errors"]:
            raise RuntimeError("cannot retire a hash-drifted or invalid incubation record")
        if current["status"] in {"FAILED", "RETIRED"}:
            raise RuntimeError(f"cannot retire a terminal incubation with status {current['status']}")
        plan = ForwardIncubationPlanV1.model_validate(current["plan"])
        self._append_event(
            plan,
            {
                "event_type": "retirement",
                "actor": retired_by,
                "notes": reason,
                "retirement_reason": reason,
            },
        )
        return self.detail(campaign_id, variant_id, attempt_id)

    def list(self, *, campaign_id: str | None = None) -> list[dict[str, Any]]:
        campaign = _validated_identifier(campaign_id) if campaign_id is not None else None
        base = self.root / campaign if campaign else self.root
        if not base.is_dir():
            return []
        depth = "*/*/" + PLAN_FILENAME if campaign else "*/*/*/" + PLAN_FILENAME
        records = []
        for plan_path in sorted(base.glob(depth)):
            relative = plan_path.parent.relative_to(self.root)
            if len(relative.parts) != 3:
                continue
            records.append(self.detail(*relative.parts))
        return records

    def detail(self, campaign_id: str, variant_id: str, attempt_id: str) -> dict[str, Any]:
        campaign = _validated_identifier(campaign_id)
        variant = _validated_identifier(variant_id)
        attempt = _validated_identifier(attempt_id)
        directory = self._record_dir(campaign, variant, attempt)
        plan_path = directory / PLAN_FILENAME
        if not plan_path.is_file():
            raise FileNotFoundError("forward incubation was not found")
        errors: list[str] = []
        try:
            plan_bytes = plan_path.read_bytes()
            plan = ForwardIncubationPlanV1.model_validate(json.loads(plan_bytes))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return _invalid_detail(campaign, variant, attempt, f"invalid incubation plan: {exc}")
        if (plan.campaign_id, plan.variant_id, plan.attempt_id) != (campaign, variant, attempt):
            errors.append("plan identity does not match its immutable storage path")
        plan_sha256 = _sha256_bytes(plan_bytes)
        try:
            receipt = (directory / PLAN_RECEIPT_FILENAME).read_text(encoding="ascii").strip()
            if receipt != plan_sha256:
                errors.append("incubation plan hash receipt is stale or mismatched")
        except OSError as exc:
            errors.append(f"incubation plan hash receipt is unavailable: {exc}")

        review_path = resolve_recorded_path(plan.candidate_review_path, project_root=self.project_root)
        result_path = resolve_recorded_path(plan.result_bundle_path, project_root=self.project_root)
        config_path = resolve_recorded_path(plan.config_path, project_root=self.project_root)
        for label, path, expected in (
            ("candidate review", review_path, plan.candidate_review_sha256),
            ("result bundle", result_path, plan.result_bundle_sha256),
            ("config", config_path, plan.config_sha256),
        ):
            try:
                if _file_sha256(path) != expected:
                    errors.append(f"{label} hash is stale or mismatched")
            except OSError as exc:
                errors.append(f"{label} is unavailable: {exc}")

        try:
            report = CandidateReviewService().inspect(
                candidate_review_path=review_path,
                result_bundle_path=result_path,
                config_path=config_path,
            )
            if not report.get("valid"):
                errors.extend(
                    "candidate review is no longer current: " + str(item)
                    for item in report.get("errors") or ["verification failed"]
                )
            else:
                review = report.get("review")
                if not isinstance(review, CandidateReviewV1) or review.decision != "approved_candidate":
                    errors.append("source candidate review is not an approved candidate decision")
                elif (review.campaign_id, review.variant_id, review.run_id) != (
                    plan.campaign_id,
                    plan.variant_id,
                    plan.run_id,
                ):
                    errors.append("source candidate-review identity is stale or mismatched")
                if isinstance(review, CandidateReviewV1) and review.config_hash != plan.governed_config_hash:
                    errors.append("governed config hash is stale or mismatched")
        except (OSError, ValueError) as exc:
            errors.append(f"candidate-review verification failed: {exc}")

        try:
            cfg = _load_yaml(config_path)
            config_identity = (
                str(cfg.get("campaign_id") or ""),
                str(cfg.get("variant_id") or config_path.parent.name),
                str(cfg.get("attempt_id") or "original"),
            )
            if config_identity != (plan.campaign_id, plan.variant_id, plan.attempt_id):
                errors.append("current config identity is stale or mismatched")
            objectives, objectives_sha256 = _validated_objectives(cfg)
            if objectives_sha256 != plan.research_objectives_sha256:
                errors.append("research-objectives hash is stale or mismatched")
            if _thresholds_from_objectives(objectives) != plan.thresholds:
                errors.append("incubation thresholds no longer match the frozen objectives and policy floors")
        except (OSError, ValueError) as exc:
            errors.append(f"research objectives are unavailable or invalid: {exc}")

        events, journal_errors, events_sha256 = self._load_events(directory, plan, plan_sha256)
        errors.extend(journal_errors)
        evidence_root = (directory / EVIDENCE_DIRECTORY).resolve()
        for event in events:
            if event.evidence_path is None or event.evidence_sha256 is None:
                continue
            attachment = directory / event.evidence_path
            try:
                resolved_attachment = attachment.resolve(strict=True)
                resolved_attachment.relative_to(evidence_root)
                if attachment.is_symlink() or not resolved_attachment.is_file():
                    raise ValueError("attachment is not a regular immutable file")
                if _file_sha256(resolved_attachment) != event.evidence_sha256:
                    raise ValueError("attachment hash is stale or mismatched")
            except (OSError, ValueError) as exc:
                errors.append(f"event {event.sequence} evidence is unavailable or invalid: {exc}")
        now = _aware_datetime(self._clock(), "inspection time")
        if now < plan.started_at:
            errors.append("system time precedes the immutable incubation start")
            calendar_days = 0
        else:
            calendar_days = (now.date() - plan.started_at.date()).days
        trade_count = sum(event.trade_count_delta or 0 for event in events if event.event_type == "observation")
        net_pnl = sum(event.net_pnl_delta or 0.0 for event in events if event.event_type == "observation")
        status: ForwardIncubationStatus
        if errors:
            status = "NEEDS MANUAL REVIEW"
        else:
            status = _derive_status(
                events,
                calendar_days=calendar_days,
                trade_count=trade_count,
                thresholds=plan.thresholds,
            )
        return {
            "schema": "alphaquest.forward-incubation-detail/v1",
            "campaign_id": campaign,
            "variant_id": variant,
            "attempt_id": attempt,
            "status": status,
            "candidate_only": True,
            "automatic_pass_permitted": False,
            "calendar_days": calendar_days,
            "trade_count": trade_count,
            "net_pnl": net_pnl,
            "minimum_calendar_days": plan.thresholds.minimum_calendar_days,
            "minimum_trades": plan.thresholds.minimum_trades,
            "duration_threshold_met": calendar_days >= plan.thresholds.minimum_calendar_days,
            "trade_threshold_met": trade_count >= plan.thresholds.minimum_trades,
            "plan_sha256": plan_sha256,
            "plan_path": _recorded_path(plan_path, self.project_root),
            "events_path": _recorded_path(directory / EVENTS_FILENAME, self.project_root),
            "events_sha256": events_sha256,
            "event_count": len(events),
            "last_event_sha256": events[-1].event_sha256 if events else plan_sha256,
            "plan": plan.model_dump(mode="json", by_alias=True),
            "events": [event.model_dump(mode="json", by_alias=True) for event in events],
            "errors": errors,
        }

    def _record_dir(self, campaign_id: str, variant_id: str, attempt_id: str) -> Path:
        return self.root / campaign_id / variant_id / attempt_id

    def _find_current_candidate(self, campaign_id: str, variant_id: str, attempt_id: str) -> tuple[Path, Path, Path]:
        matches: list[tuple[Path, Path, Path]] = []
        blockers: list[str] = []
        for evidence_root in self.layout.evidence_roots:
            for review_path in sorted(evidence_root.glob("**/candidate_review*.json")):
                try:
                    raw = json.loads(review_path.read_text(encoding="utf-8"))
                    review = CandidateReviewV1.model_validate(raw)
                except (OSError, json.JSONDecodeError, ValueError):
                    continue
                if (review.campaign_id, review.variant_id) != (campaign_id, variant_id):
                    continue
                result_path = review_path.parent / RESULT_BUNDLE_FILENAME
                manifest_path = review_path.parent / "finalization_manifest.json"
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    config_path = resolve_recorded_path(
                        str(manifest.get("source_config") or ""),
                        project_root=self.project_root,
                    )
                    cfg = _load_yaml(config_path)
                except (OSError, json.JSONDecodeError, ValueError) as exc:
                    blockers.append(str(exc))
                    continue
                if str(cfg.get("attempt_id") or "original") != attempt_id:
                    continue
                report = CandidateReviewService().inspect(
                    candidate_review_path=review_path,
                    result_bundle_path=result_path,
                    config_path=config_path,
                )
                verified = report.get("review")
                if (
                    report.get("valid")
                    and isinstance(verified, CandidateReviewV1)
                    and verified.decision == "approved_candidate"
                    and verified.lifecycle_state == "candidate"
                ):
                    matches.append((review_path.resolve(), result_path.resolve(), config_path.resolve()))
                else:
                    blockers.extend(str(item) for item in report.get("errors") or ["candidate is not approved"])
        if len(matches) > 1:
            raise ValueError("multiple current approved candidate records match this campaign/variant/attempt")
        if not matches:
            if blockers:
                raise ValueError(
                    "matching candidate evidence is not current and hash-valid: " + "; ".join(blockers)
                )
            raise FileNotFoundError("no current approved candidate record matches this campaign/variant/attempt")
        return matches[0]

    def _append_event(self, plan: ForwardIncubationPlanV1, values: Mapping[str, Any]) -> None:
        directory = self._record_dir(plan.campaign_id, plan.variant_id, plan.attempt_id)
        plan_path = directory / PLAN_FILENAME
        plan_sha256 = _file_sha256(plan_path)
        events_path = directory / EVENTS_FILENAME
        occurred_at = _aware_datetime(self._clock(), "occurred_at")
        with events_path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.seek(0)
            raw = handle.read()
            events, errors = _parse_event_bytes(raw, plan, plan_sha256)
            errors.extend(_validate_event_head(directory, raw, events, plan_sha256))
            if errors:
                raise RuntimeError("cannot append to an invalid event journal: " + "; ".join(errors))
            last_time = events[-1].occurred_at if events else plan.started_at
            if occurred_at <= last_time:
                raise ValueError("server time must advance; backdated or duplicate-time events are forbidden")
            previous = events[-1].event_sha256 if events else plan_sha256
            payload = {
                "schema": FORWARD_INCUBATION_EVENT_SCHEMA,
                "sequence": len(events) + 1,
                "occurred_at": occurred_at.isoformat(),
                "plan_sha256": plan_sha256,
                "previous_event_sha256": previous,
                **dict(values),
            }
            # Validate and materialize every event-type default before hashing,
            # so the digest is over the exact JSON object written to disk.
            payload["event_sha256"] = "0" * 64
            normalized = ForwardIncubationEventV1.model_validate(payload).model_dump(
                mode="json", by_alias=True
            )
            normalized["event_sha256"] = _event_sha256(normalized)
            event = ForwardIncubationEventV1.model_validate(normalized)
            encoded_event = _json_bytes(event.model_dump(mode="json", by_alias=True), pretty=False) + b"\n"
            handle.seek(0, os.SEEK_END)
            handle.write(encoded_event)
            handle.flush()
            os.fsync(handle.fileno())
            _atomic_write_bytes(
                directory / EVENT_HEAD_FILENAME,
                _json_bytes(
                    _event_head_payload(
                        len(events) + 1,
                        event.event_sha256,
                        _sha256_bytes(raw + encoded_event),
                    ),
                    pretty=True,
                ),
            )
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _load_events(
        self,
        directory: Path,
        plan: ForwardIncubationPlanV1,
        plan_sha256: str,
    ) -> tuple[list[ForwardIncubationEventV1], list[str], str | None]:
        try:
            with (directory / EVENTS_FILENAME).open("rb") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
                raw = handle.read()
                events, errors = _parse_event_bytes(raw, plan, plan_sha256)
                errors.extend(_validate_event_head(directory, raw, events, plan_sha256))
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            return events, errors, _sha256_bytes(raw)
        except OSError as exc:
            return [], [f"incubation event journal is unavailable: {exc}"], None


def _derive_status(
    events: list[ForwardIncubationEventV1],
    *,
    calendar_days: int,
    trade_count: int,
    thresholds: ForwardIncubationThresholdsV1,
) -> ForwardIncubationStatus:
    if any(event.event_type == "retirement" for event in events):
        return "RETIRED"
    if any(
        event.event_type == "observation"
        and (
            event.prop_rule_breach
            or event.forced_flatten_violation
            or bool(event.triggered_abandonment_rules)
        )
        for event in events
    ) or any(event.event_type == "review" and event.review_decision == "fail" for event in events):
        return "FAILED"
    latest_review = next((event for event in reversed(events) if event.event_type == "review"), None)
    if latest_review is not None and latest_review.review_decision == "needs_manual_review":
        return "NEEDS MANUAL REVIEW"
    if calendar_days >= thresholds.minimum_calendar_days and trade_count >= thresholds.minimum_trades:
        return "ELIGIBLE_FOR_REVIEW"
    return "ACTIVE"


def _parse_event_bytes(
    raw: bytes,
    plan: ForwardIncubationPlanV1,
    plan_sha256: str,
) -> tuple[list[ForwardIncubationEventV1], list[str]]:
    events: list[ForwardIncubationEventV1] = []
    errors: list[str] = []
    previous_hash = plan_sha256
    previous_time = plan.started_at
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [], [f"event journal is not UTF-8: {exc}"]
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            errors.append(f"event journal line {line_number} is blank")
            continue
        try:
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError("event must be a JSON object")
            event = ForwardIncubationEventV1.model_validate(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"invalid event journal line {line_number}: {exc}")
            continue
        if event.sequence != line_number:
            errors.append(f"event sequence is non-contiguous at line {line_number}")
        if event.plan_sha256 != plan_sha256:
            errors.append(f"event plan hash is stale or mismatched at line {line_number}")
        if event.previous_event_sha256 != previous_hash:
            errors.append(f"event hash chain is broken at line {line_number}")
        if event.event_sha256 != _event_sha256(payload):
            errors.append(f"event content hash is stale or mismatched at line {line_number}")
        if event.occurred_at <= previous_time:
            errors.append(f"event chronology is non-increasing at line {line_number}")
        unknown = sorted(set(event.triggered_abandonment_rules) - set(plan.thresholds.abandonment_rules))
        if unknown:
            errors.append(f"event cites undeclared abandonment rules at line {line_number}: {', '.join(unknown)}")
        events.append(event)
        previous_hash = event.event_sha256
        previous_time = event.occurred_at
    return events, errors


def _event_head_payload(event_count: int, last_event_sha256: str, journal_sha256: str) -> dict[str, Any]:
    return {
        "schema": FORWARD_INCUBATION_EVENT_HEAD_SCHEMA,
        "event_count": event_count,
        "last_event_sha256": last_event_sha256,
        "journal_sha256": journal_sha256,
    }


def _validate_event_head(
    directory: Path,
    raw: bytes,
    events: list[ForwardIncubationEventV1],
    plan_sha256: str,
) -> list[str]:
    try:
        payload = json.loads((directory / EVENT_HEAD_FILENAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"event-head receipt is unavailable or invalid: {exc}"]
    if not isinstance(payload, dict):
        return ["event-head receipt must contain a JSON object"]
    errors: list[str] = []
    expected_keys = {"schema", "event_count", "last_event_sha256", "journal_sha256"}
    if set(payload) != expected_keys:
        errors.append("event-head receipt fields are invalid")
    if payload.get("schema") != FORWARD_INCUBATION_EVENT_HEAD_SCHEMA:
        errors.append("event-head receipt schema is invalid")
    if payload.get("event_count") != len(events):
        errors.append("event-head count does not match the append-only journal")
    expected_last = events[-1].event_sha256 if events else plan_sha256
    if payload.get("last_event_sha256") != expected_last:
        errors.append("event-head last hash does not match the append-only journal")
    if payload.get("journal_sha256") != _sha256_bytes(raw):
        errors.append("event-head journal hash is stale or mismatched")
    return errors


def _thresholds_from_objectives(objectives: ResearchObjectivesV1) -> ForwardIncubationThresholdsV1:
    return ForwardIncubationThresholdsV1(
        minimum_calendar_days=max(MINIMUM_CALENDAR_DAYS, objectives.forward_incubation_min_calendar_days),
        minimum_trades=max(MINIMUM_TRADES, objectives.forward_incubation_min_trades),
        abandonment_rules=objectives.abandonment_rules,
        retirement_rules=objectives.retirement_rules,
    )


def _validated_objectives(config: Mapping[str, Any]) -> tuple[ResearchObjectivesV1, str]:
    raw = config.get("research_objectives")
    if not isinstance(raw, Mapping):
        raise ValueError("config does not contain frozen research objectives")
    objectives = ResearchObjectivesV1.model_validate(dict(raw))
    digest = _object_sha256(dict(raw))
    declared = str(config.get("research_objectives_sha256") or "")
    if declared != digest:
        raise ValueError("declared research-objectives SHA-256 is missing, stale, or mismatched")
    return objectives, digest


def _event_sha256(payload: Mapping[str, Any]) -> str:
    material = {key: value for key, value in payload.items() if key != "event_sha256"}
    return _object_sha256(material)


def _object_sha256(value: Any) -> str:
    return _sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_json_default).encode(
            "utf-8"
        )
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"cannot serialize {type(value).__name__}")


def _json_bytes(value: Any, *, pretty: bool) -> bytes:
    return (
        json.dumps(
            value,
            indent=2 if pretty else None,
            sort_keys=True,
            separators=None if pretty else (",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + ("\n" if pretty else "")
    ).encode("utf-8")


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"could not read config: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("config must contain a YAML mapping")
    return value


def _recorded_path(path: Path, project_root: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return str(path)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _validated_identifier(value: str) -> str:
    cleaned = str(value).strip()
    if _IDENTIFIER.fullmatch(cleaned) is None:
        raise ValueError("incubation identity must be lowercase letters, digits, or underscores")
    return cleaned


def _validated_sha256(value: str) -> str:
    cleaned = str(value).strip()
    if _SHA256.fullmatch(cleaned) is None:
        raise ValueError("value must be a lowercase SHA-256 digest")
    return cleaned


def _aware_datetime(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value


def _write_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _invalid_detail(campaign_id: str, variant_id: str, attempt_id: str, error: str) -> dict[str, Any]:
    return {
        "schema": "alphaquest.forward-incubation-detail/v1",
        "campaign_id": campaign_id,
        "variant_id": variant_id,
        "attempt_id": attempt_id,
        "status": "NEEDS MANUAL REVIEW",
        "candidate_only": True,
        "automatic_pass_permitted": False,
        "calendar_days": 0,
        "trade_count": 0,
        "net_pnl": 0.0,
        "minimum_calendar_days": None,
        "minimum_trades": None,
        "duration_threshold_met": False,
        "trade_threshold_met": False,
        "plan_sha256": None,
        "plan_path": None,
        "events_path": None,
        "events_sha256": None,
        "event_count": 0,
        "last_event_sha256": None,
        "plan": None,
        "events": [],
        "errors": [error],
    }


__all__ = [
    "EVENTS_FILENAME",
    "EVENT_HEAD_FILENAME",
    "EVIDENCE_DIRECTORY",
    "FORWARD_INCUBATION_DIRECTORY",
    "FORWARD_INCUBATION_EVENT_HEAD_SCHEMA",
    "FORWARD_INCUBATION_EVENT_SCHEMA",
    "FORWARD_INCUBATION_PLAN_SCHEMA",
    "ForwardIncubationEventV1",
    "ForwardIncubationPlanV1",
    "ForwardIncubationService",
    "ForwardIncubationStatus",
    "ForwardIncubationThresholdsV1",
    "MINIMUM_CALENDAR_DAYS",
    "MINIMUM_TRADES",
    "PLAN_FILENAME",
]
