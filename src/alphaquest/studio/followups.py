"""Governed, immutable follow-up attempts for Research Studio campaigns.

The authored definitions are never edited by a follow-up. Every explicit
follow-up is installed as a complete current-variant source subtree with fresh
mechanics-validation, approval, and staged-run identities.  Creating an
attempt and queueing it are separate operations: the former creates new
scientific lineage, while repeated queue submission for that identity remains
idempotent.
"""

from __future__ import annotations

from copy import deepcopy
import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
from typing import Any, Callable, Literal, Mapping
from uuid import uuid4

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import yaml

from alphaquest.accounts.models import AccountAssessmentCostsV1
from alphaquest.authoring.catalog import CERTIFIED_MODULE_CATALOG
from alphaquest.authoring.compiler import (
    AUTHORING_MANIFEST_SCHEMA,
    STRATEGY_SPEC_SCHEMA,
    mechanics_validation_subset,
)
from alphaquest.authoring.models import (
    DatasetManifestV1,
    ModuleBindingV1,
    ResearchObjectivesV1,
)
from alphaquest.research.definitions import write_definition_manifests
from alphaquest.research.campaign_stages import (
    DEFAULT_STAGE_ORDER,
    canonicalize_campaign_config,
    campaign_test_data_window_plan,
)
from alphaquest.research.policy import load_research_policy
from alphaquest.research.factory_policy import research_factory_binding
from alphaquest.research.experiment_registry import ExperimentRegistry
from alphaquest.research.preflight import run_preflight
from alphaquest.research.schemas import validate_campaign_config_contract
from alphaquest.research.storage import load_storage_layout
from alphaquest.studio.approvals import require_all_variant_mechanics_approved
from alphaquest.studio.finalization import REPORTING_DIRECTORY, inspect_finalized_result
from alphaquest.studio.jobs import JobRecordV1, OperationalState, SQLiteJobQueue
from alphaquest.studio.ledger import append_planned_follow_up
from alphaquest.studio.results import RESULT_BUNDLE_FILENAME
from alphaquest.studio.workspace import refresh_generated_indexes_if_stale
from alphaquest.strategy_certification import (
    StrategyCertificationError,
    apply_certified_execution_contract,
    get_strategy_certification,
    normalize_certified_event_params,
    strategy_identity_for_config,
    validate_certified_parameter_value,
    validate_certified_event_parameter_grid,
)
from alphaquest.validation.promotion_gate import inspect_validation_gate


FOLLOW_UP_SCHEMA = "alphaquest.follow-up-attempt/v1"
FOLLOW_UP_ROOT = "follow_up_attempts"
ATTEMPT_KINDS = (
    "replication",
    "data_refresh",
    "methodology_rerun",
    "pre_pnl_protocol_declaration",
    "pre_pnl_mechanics_correction",
    "pre_pnl_parameter_declaration",
    "rescue",
)
AttemptKind = Literal[
    "replication",
    "data_refresh",
    "methodology_rerun",
    "pre_pnl_protocol_declaration",
    "pre_pnl_mechanics_correction",
    "pre_pnl_parameter_declaration",
    "rescue",
]
JsonScalar = str | int | float | bool | None
TARGET_VARIANT_PERFORMANCE_SCOPE = "target_variant_v1"
DESTINATION_BENCHMARK_SCHEMA = "alphaquest.destination-benchmark-contract/v1"


class MechanicParameterPatchV1(BaseModel):
    """One explicit scalar correction inside an existing certified module."""

    model_config = ConfigDict(extra="forbid", strict=True)

    variant_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_]*$")
    component: Literal["entry", "sl", "tp"]
    parameter_path: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_.]*$")
    value: JsonScalar

    @field_validator("value")
    @classmethod
    def finite_value(cls, value: JsonScalar) -> JsonScalar:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("mechanics patch values must be finite")
        return value


class MechanicsValidationWindowV1(BaseModel):
    """One predeclared mechanics-review data window for a frozen variant."""

    model_config = ConfigDict(extra="forbid", strict=True)

    variant_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_]*$")
    start_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    session_count: int = Field(
        default_factory=lambda: int(
            load_research_policy().mechanics_validation["session_count"]
        )
    )

    @model_validator(mode="after")
    def bounded_window(self) -> "MechanicsValidationWindowV1":
        try:
            start = date.fromisoformat(self.start_date)
            end = date.fromisoformat(self.end_date)
        except ValueError as exc:
            raise ValueError("mechanics validation dates must be valid ISO dates") from exc
        if end < start:
            raise ValueError("mechanics validation end_date cannot precede start_date")
        required = int(load_research_policy().mechanics_validation["session_count"])
        if self.session_count != required:
            raise ValueError(
                f"mechanics validation must use the repository-wide {required}-session policy"
            )
        if (end - start).days > 60:
            raise ValueError("mechanics validation window cannot exceed 60 calendar days")
        return self


class ExecutionTimelinePatchV1(BaseModel):
    """Atomic event-lane entry cutoff, flatten, and daily-limit correction."""

    model_config = ConfigDict(extra="forbid", strict=True)

    latest_entry_time: str = Field(pattern=r"^\d{2}:\d{2}:\d{2}$")
    flatten_time: str = Field(pattern=r"^\d{2}:\d{2}:\d{2}$")
    max_trades_per_day: int = Field(ge=0)

    @model_validator(mode="after")
    def causal_timeline(self) -> "ExecutionTimelinePatchV1":
        if self.latest_entry_time >= self.flatten_time:
            raise ValueError("latest_entry_time must precede flatten_time")
        return self


class DestinationBenchmarkSelectionV1(BaseModel):
    """One pre-PnL, versioned account destination and its observed costs."""

    model_config = ConfigDict(extra="forbid", strict=True)

    profile_id: str = Field(min_length=1)
    profile_version: str = Field(min_length=1)
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    role: Literal["primary", "comparison"]
    costs: AccountAssessmentCostsV1 | None = None
    benchmark_acknowledged: Literal[True]

    @model_validator(mode="after")
    def costs_are_time_bound(self) -> "DestinationBenchmarkSelectionV1":
        if self.costs is not None:
            observed_at = self.costs.observed_at
            if observed_at.tzinfo is None or observed_at.utcoffset() is None:
                raise ValueError("destination benchmark costs must use a timezone-aware observed_at")
        return self


class FollowUpAttemptRequestV1(BaseModel):
    """Strict human-reviewed request for a new scientific attempt identity."""

    model_config = ConfigDict(extra="forbid", strict=True)

    campaign_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_]*$")
    attempt_kind: AttemptKind
    parent_attempt_id: str = Field(default="original", pattern=r"^[a-z0-9][a-z0-9_]*$")
    reason: str = Field(min_length=80)
    created_by: str = Field(min_length=1)
    dataset_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_]*$")
    target_variant_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_]*$")
    authorized_by: str | None = None
    mechanic_patches: list[MechanicParameterPatchV1] = Field(default_factory=list)
    refresh_certification: bool = False
    replacement_strategy_id: str | None = Field(
        default=None,
        pattern=r"^[a-z0-9][a-z0-9_]*$",
    )
    parameter_grid: dict[str, list[JsonScalar]] = Field(default_factory=dict)
    mechanics_validation_window: MechanicsValidationWindowV1 | None = None
    execution_timeline: ExecutionTimelinePatchV1 | None = None
    research_objectives: ResearchObjectivesV1 | None = None
    destination_benchmarks: list[DestinationBenchmarkSelectionV1] = Field(
        default_factory=list,
        max_length=8,
    )
    destination_scope_acknowledged: bool = False

    @field_validator("reason", "created_by", "authorized_by")
    @classmethod
    def normalized_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def kind_specific_contract(self) -> "FollowUpAttemptRequestV1":
        if len(self.reason) < 80:
            raise ValueError("reason must contain at least 80 characters after trimming")
        if not self.created_by:
            raise ValueError("created_by must identify the researcher")
        mechanics_kind = self.attempt_kind in {"pre_pnl_mechanics_correction", "rescue"}
        declaration_kind = self.attempt_kind == "pre_pnl_parameter_declaration"
        protocol_kind = self.attempt_kind == "pre_pnl_protocol_declaration"
        if self.attempt_kind == "data_refresh" and not self.dataset_id:
            raise ValueError("data_refresh requires a governed dataset_id")
        if self.attempt_kind != "data_refresh" and self.dataset_id is not None:
            raise ValueError("dataset_id is only valid for data_refresh")
        if mechanics_kind and not self.target_variant_id:
            raise ValueError(f"{self.attempt_kind} requires a target variant")
        if self.attempt_kind == "pre_pnl_mechanics_correction":
            modes = sum(
                (
                    bool(self.mechanic_patches),
                    bool(self.refresh_certification),
                    self.execution_timeline is not None,
                )
            )
            if modes != 1:
                raise ValueError(
                    "pre_pnl_mechanics_correction requires exactly one of an explicit "
                    "mechanics patch, a certified implementation refresh, or an "
                    "atomic execution-timeline correction"
                )
        if self.attempt_kind == "rescue" and not self.mechanic_patches:
            raise ValueError("rescue requires an explicit mechanics patch")
        if self.refresh_certification and self.attempt_kind not in {
            "pre_pnl_mechanics_correction",
            "methodology_rerun",
        }:
            raise ValueError(
                "refresh_certification is reserved for a pre-PnL mechanics correction "
                "or a methodology rerun with a fixed mechanics window"
            )
        if (
            self.attempt_kind == "methodology_rerun"
            and self.refresh_certification
            and self.mechanics_validation_window is None
        ):
            raise ValueError(
                "methodology_rerun certification refresh requires a fixed mechanics validation window"
            )
        if (
            self.execution_timeline is not None
            and self.attempt_kind != "pre_pnl_mechanics_correction"
        ):
            raise ValueError(
                "execution_timeline is reserved for pre_pnl_mechanics_correction"
            )
        if self.replacement_strategy_id and not self.refresh_certification:
            raise ValueError(
                "replacement_strategy_id requires a pre-PnL certification refresh"
            )
        if (
            self.replacement_strategy_id
            and self.attempt_kind != "pre_pnl_mechanics_correction"
        ):
            raise ValueError(
                "replacement_strategy_id is reserved for pre_pnl_mechanics_correction"
            )
        if declaration_kind and (not self.target_variant_id or not self.parameter_grid):
            raise ValueError("pre_pnl_parameter_declaration requires a target variant and parameter grid")
        if protocol_kind and (not self.target_variant_id or self.research_objectives is None):
            raise ValueError(
                "pre_pnl_protocol_declaration requires a target variant and confirmed research objectives"
            )
        if not protocol_kind and self.research_objectives is not None:
            raise ValueError(
                "research_objectives are reserved for pre_pnl_protocol_declaration"
            )
        if not protocol_kind and (
            self.destination_benchmarks or self.destination_scope_acknowledged
        ):
            raise ValueError(
                "destination benchmarks are reserved for pre_pnl_protocol_declaration"
            )
        if protocol_kind and not self.destination_benchmarks:
            raise ValueError(
                "pre_pnl_protocol_declaration requires one primary destination benchmark"
            )
        if self.destination_benchmarks:
            identities = [
                (item.profile_id, item.profile_version)
                for item in self.destination_benchmarks
            ]
            if len(identities) != len(set(identities)):
                raise ValueError("destination benchmark profiles must be unique")
            primary_count = sum(
                item.role == "primary" for item in self.destination_benchmarks
            )
            if primary_count != 1:
                raise ValueError(
                    "destination benchmarks require exactly one primary profile"
                )
            if not self.destination_scope_acknowledged:
                raise ValueError(
                    "destination benchmark scope must be explicitly acknowledged"
                )
        elif self.destination_scope_acknowledged:
            raise ValueError(
                "destination scope acknowledgment requires at least one benchmark profile"
            )
        target_allowed = (
            mechanics_kind
            or declaration_kind
            or protocol_kind
            or self.attempt_kind == "data_refresh"
            or self.attempt_kind == "replication"
            or self.attempt_kind == "methodology_rerun"
        )
        if not target_allowed and (
            self.target_variant_id is not None
            or self.mechanic_patches
            or self.refresh_certification
            or self.replacement_strategy_id
            or self.parameter_grid
            or self.execution_timeline is not None
            or self.research_objectives is not None
            or self.destination_benchmarks
            or self.destination_scope_acknowledged
        ):
            raise ValueError(
                "target_variant_id is valid only for replication or governed variant-scoped changes; "
                "mechanic_patches and parameter_grid require their corresponding governed change type"
            )
        if declaration_kind and self.mechanic_patches:
            raise ValueError("parameter declaration cannot also patch fixed mechanics")
        if mechanics_kind and self.parameter_grid:
            raise ValueError("mechanics correction and rescue cannot also redeclare the parameter grid")
        if protocol_kind and (
            self.mechanic_patches
            or self.refresh_certification
            or self.replacement_strategy_id
            or self.parameter_grid
            or self.execution_timeline is not None
        ):
            raise ValueError(
                "pre-PnL protocol declaration cannot also change mechanics, certification, parameters, or execution"
            )
        if self.target_variant_id and any(
            patch.variant_id != self.target_variant_id for patch in self.mechanic_patches
        ):
            raise ValueError("every mechanics patch must target the declared target_variant_id")
        if self.attempt_kind == "rescue" and not self.authorized_by:
            raise ValueError("rescue requires an explicitly identified authorizer")
        if self.attempt_kind != "rescue" and self.authorized_by is not None:
            raise ValueError("authorized_by is reserved for the governed rescue lane")
        if (
            self.attempt_kind != "methodology_rerun"
            and self.mechanics_validation_window is not None
        ):
            raise ValueError(
                "mechanics_validation_window is reserved for methodology_rerun"
            )
        for name, values in self.parameter_grid.items():
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None:
                raise ValueError(f"invalid certified event parameter name: {name!r}")
            if not isinstance(values, list) or len(values) < 2:
                raise ValueError(f"parameter grid {name!r} must contain at least two values")
        return self


@dataclass(frozen=True)
class FollowUpAttemptResult:
    campaign_id: str
    attempt_id: str
    attempt_kind: str
    parent_attempt_id: str
    destination: Path
    manifest_path: Path
    config_paths: tuple[Path, ...]
    config_sha256: Mapping[str, str]
    ledger_rows_appended: int
    indexes_refreshed: bool
    next_action: str = (
        "Generate fresh mechanics evidence for the current sequential variant, review it, and record a new hash-bound approval."
    )
    preflight_verdict: str = "PASS"


def _require_queueable_performance_job(job: JobRecordV1, *, attempt_id: str) -> None:
    if job.state in {
        OperationalState.QUEUED,
        OperationalState.RUNNING,
        OperationalState.CANCEL_REQUESTED,
    }:
        return
    raise ValueError(
        "Performance submission blocked: attempt "
        f"{attempt_id!r} already has terminal Campaign Variant Run "
        f"{job.job_id} ({job.state.value}). Interrupted or completed attempts are never replayed. "
        "Open Research > History, create an Exact replication from this attempt, complete its "
        "hash-bound mechanics approval, then run the full test suite for the new attempt."
    )


def _performance_hash_locks(gate: Mapping[str, Any]) -> dict[str, str]:
    approval_path = Path(str(gate.get("approval_path") or ""))
    locks = {
        "config_hash": str(gate.get("config_hash") or ""),
        "input_data_hash": str(gate.get("input_data_hash") or ""),
        "mechanics_approval_sha256": (
            _file_sha256(approval_path) if approval_path.is_file() else ""
        ),
    }
    missing = sorted(name for name, value in locks.items() if not value)
    if missing:
        raise ValueError(
            "Performance submission is missing mandatory hash locks: "
            + ", ".join(missing)
        )
    for name in (
        "strategy_implementation_sha256",
        "strategy_certification_manifest_sha256",
    ):
        value = str(gate.get(name) or "")
        if value:
            locks[name] = value
    return locks


def _is_legacy_unreserved_preflight_only_job(job: JobRecordV1) -> bool:
    """Recognize an old campaign-wide preflight that never started testing."""

    if (
        job.job_type != "campaign_variant_run"
        or job.attempt_reserved
        or job.state != OperationalState.SUCCEEDED
        or job.payload.get("execution_scope") is not None
        or not isinstance(job.result, Mapping)
    ):
        return False
    preflight = job.result.get("preflight")
    return (
        job.research_verdict == "NEEDS MANUAL REVIEW"
        and job.result.get("reason") == "full staged-submission preflight failed"
        and isinstance(preflight, Mapping)
        and preflight.get("passed") is False
        and preflight.get("tests_ran") is False
    )


class FollowUpAttemptService:
    """Create and submit explicit follow-ups without mutating prior attempts."""

    def __init__(
        self,
        project_root: str | Path = ".",
        *,
        now: Callable[[], datetime] | None = None,
        token: Callable[[], str] | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.layout = load_storage_layout(self.project_root)
        self._now = now or (lambda: datetime.now(UTC))
        self._token = token or (lambda: uuid4().hex[:8])

    def parent_has_performance_evidence(
        self,
        campaign_id: str,
        parent_attempt_id: str,
    ) -> bool:
        """Return whether a parent is past the pre-PnL follow-up boundary.

        Studio uses this same authoritative evidence check when presenting
        follow-up choices. Creation repeats the check in ``_require_kind_policy``
        so callers still fail closed if state changes before submission.
        """

        campaign_root, campaign, variants = self._campaign(campaign_id)
        self._require_studio_authored(campaign_root, campaign, variants)
        parent_paths = self.config_paths(campaign_id, parent_attempt_id)
        parent_path_by_variant = {path.parent.name: path for path in parent_paths}
        parent_configs = {
            path.parent.name: _read_yaml(path) for path in parent_paths
        }
        return _attempt_has_performance_evidence(
            self.layout.evidence_roots,
            self.layout.studio_runtime_root,
            self.project_root,
            campaign_id,
            parent_attempt_id,
            parent_configs,
            parent_path_by_variant,
        )

    def create(
        self,
        request: FollowUpAttemptRequestV1 | Mapping[str, Any],
    ) -> FollowUpAttemptResult:
        parsed = FollowUpAttemptRequestV1.model_validate(
            request.model_dump(mode="python") if isinstance(request, FollowUpAttemptRequestV1) else dict(request)
        )
        campaign_root, campaign, variants = self._campaign(parsed.campaign_id)
        self._require_studio_authored(campaign_root, campaign, variants)
        parent_paths = self.config_paths(parsed.campaign_id, parsed.parent_attempt_id)
        frozen_parent_variants = tuple(path.parent.name for path in parent_paths)
        if len(set(frozen_parent_variants)) != len(frozen_parent_variants):
            raise ValueError("parent attempt contains duplicate variant identities")
        unknown_parent_variants = sorted(set(frozen_parent_variants) - set(variants))
        if unknown_parent_variants:
            raise ValueError(
                "parent attempt contains variants outside the campaign: "
                + ", ".join(unknown_parent_variants)
            )
        # A child attempt inherits the parent's frozen scope. In particular,
        # a v02-only replication must never expand back into v01 merely because
        # both variants remain historical members of the same campaign.
        variants = frozen_parent_variants
        parent_path_by_variant = {path.parent.name: path for path in parent_paths}
        parent_configs = {path.parent.name: _read_yaml(path) for path in parent_paths}
        for variant, cfg in parent_configs.items():
            if str(cfg.get("attempt_id") or "") != parsed.parent_attempt_id:
                raise ValueError(f"parent config {variant} does not declare attempt_id={parsed.parent_attempt_id}")

        attempt_id = self._new_attempt_id(parsed.attempt_kind, campaign_root)
        destination = campaign_root / FOLLOW_UP_ROOT / attempt_id
        self._require_kind_policy(
            parsed,
            campaign_root,
            campaign,
            parent_configs,
            parent_path_by_variant,
        )
        if parsed.attempt_kind in {
            "replication",
            "pre_pnl_protocol_declaration",
        } and parsed.target_variant_id:
            if parsed.target_variant_id not in parent_configs:
                raise ValueError(
                    f"unknown {parsed.attempt_kind} target variant: {parsed.target_variant_id}"
                )
            variants = (parsed.target_variant_id,)
        configs = {variant: deepcopy(parent_configs[variant]) for variant in variants}
        dataset_manifests = self._datasets_for_configs(configs)
        changes: list[dict[str, Any]] = []

        if parsed.attempt_kind == "pre_pnl_protocol_declaration":
            assert parsed.target_variant_id is not None
            assert parsed.research_objectives is not None
            changes.extend(
                _apply_research_objectives(
                    configs[parsed.target_variant_id],
                    parsed.research_objectives,
                    variant_id=parsed.target_variant_id,
                    today=self._now().date(),
                )
            )
            if parsed.destination_benchmarks:
                changes.extend(
                    _apply_destination_benchmarks(
                        configs[parsed.target_variant_id],
                        parsed.destination_benchmarks,
                        variant_id=parsed.target_variant_id,
                        project_root=self.project_root,
                        declared_at=self._now(),
                    )
                )
        elif parsed.attempt_kind == "methodology_rerun":
            for variant in variants:
                old_policy = deepcopy(configs[variant].get("research_policy") or {})
                configs[variant] = canonicalize_campaign_config(configs[variant])
                if old_policy != configs[variant]["research_policy"]:
                    changes.append(
                        {
                            "variant_id": variant,
                            "scope": "repository_methodology",
                            "field": "research_policy",
                            "old": old_policy,
                            "new": deepcopy(configs[variant]["research_policy"]),
                            "reviewed": True,
                        }
                    )

        if parsed.attempt_kind == "data_refresh":
            dataset_manifest = self._load_dataset(str(parsed.dataset_id))
            refresh_variants = (
                (parsed.target_variant_id,)
                if parsed.target_variant_id is not None
                else variants
            )
            for variant in refresh_variants:
                if variant not in configs:
                    raise ValueError(
                        f"unknown data refresh target variant: {variant}"
                    )
                changes.extend(
                    _apply_dataset_refresh(
                        configs[variant],
                        dataset_manifest,
                        variant_id=variant,
                        project_root=self.project_root,
                    )
                )
                dataset_manifests[variant] = dataset_manifest
        elif parsed.attempt_kind in {"pre_pnl_mechanics_correction", "rescue"}:
            assert parsed.target_variant_id is not None
            target = configs[parsed.target_variant_id]
            if parsed.refresh_certification:
                changes.extend(
                    _apply_certification_refresh(
                        target,
                        variant_id=parsed.target_variant_id,
                        project_root=self.project_root,
                        replacement_strategy_id=parsed.replacement_strategy_id,
                    )
                )
            elif parsed.execution_timeline is not None:
                changes.extend(
                    _apply_execution_timeline(
                        target,
                        parsed.execution_timeline,
                        variant_id=parsed.target_variant_id,
                    )
                )
            else:
                for patch in parsed.mechanic_patches:
                    changes.append(_apply_mechanic_patch(target, patch))
        elif parsed.attempt_kind == "pre_pnl_parameter_declaration":
            assert parsed.target_variant_id is not None
            target = configs[parsed.target_variant_id]
            changes.extend(
                _apply_parameter_declaration(
                    target,
                    parsed.parameter_grid,
                    project_root=self.project_root,
                )
            )
        elif (
            parsed.attempt_kind == "methodology_rerun"
            and parsed.mechanics_validation_window is not None
        ):
            window = parsed.mechanics_validation_window
            if window.variant_id not in configs:
                raise ValueError(
                    f"unknown mechanics validation target variant: {window.variant_id}"
                )
            window_change = _apply_mechanics_validation_window(
                configs[window.variant_id],
                window,
                dataset_manifest=dataset_manifests[window.variant_id],
                project_root=self.project_root,
            )
            if window_change is not None:
                changes.append(window_change)
            if parsed.refresh_certification:
                changes.extend(
                    _apply_certification_refresh(
                        configs[window.variant_id],
                        variant_id=window.variant_id,
                        project_root=self.project_root,
                    )
                )
            if not changes:
                raise ValueError(
                    "methodology rerun must adopt a different repository policy, "
                    "change the mechanics validation window, or refresh certification"
                )

        for variant, cfg in configs.items():
            changes.extend(
                _rebase_relocated_project_paths(
                    cfg,
                    variant_id=variant,
                    project_root=self.project_root,
                )
            )

        created_at = self._now()
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ValueError("follow-up attempt clock must return a timezone-aware datetime")
        certification_target_variant = parsed.target_variant_id
        if (
            parsed.attempt_kind == "methodology_rerun"
            and parsed.mechanics_validation_window is not None
        ):
            certification_target_variant = parsed.mechanics_validation_window.variant_id
        for variant, cfg in configs.items():
            _apply_attempt_identity(
                cfg,
                evidence_root=self.layout.evidence_roots[0],
                approval_root=self.layout.research_artifact_root / "validation_approvals",
                campaign_id=parsed.campaign_id,
                variant_id=variant,
                attempt_id=attempt_id,
                attempt_kind=parsed.attempt_kind,
                parent_attempt_id=parsed.parent_attempt_id,
                reason=parsed.reason,
                created_by=parsed.created_by,
                parent_variant_id=variant,
                rescue_target_variant_id=(parsed.target_variant_id if parsed.attempt_kind == "rescue" else None),
            )
            validate_campaign_config_contract(cfg, context=f"follow-up {attempt_id}/{variant}")
            _require_full_methodology(cfg)
            target_scoped = parsed.attempt_kind in {
                "methodology_rerun",
                "pre_pnl_protocol_declaration",
                "pre_pnl_mechanics_correction",
                "pre_pnl_parameter_declaration",
                "rescue",
            } or (
                parsed.attempt_kind == "data_refresh"
                and parsed.target_variant_id is not None
            )
            if not target_scoped or variant == certification_target_variant:
                self._validate_certified_mechanics(cfg, dataset_manifests[variant])
        _refresh_and_require_unique_mechanic_signatures(configs)

        source_hashes = {variant: _file_sha256(parent_path_by_variant[variant]) for variant in variants}
        attempt_spec = _attempt_strategy_spec(parsed, attempt_id, created_at, configs, changes)
        follow_up_root = campaign_root / FOLLOW_UP_ROOT
        follow_up_root.mkdir(parents=True, exist_ok=True)
        staging = follow_up_root / f".{attempt_id}.staging"
        if staging.exists() or staging.is_symlink():
            raise FileExistsError(f"unexpected follow-up staging collision: {staging}")
        staging.mkdir(parents=True)
        installed = False
        try:
            staged_paths: list[Path] = []
            for variant in variants:
                path = staging / variant / "config.yaml"
                _write_yaml(path, configs[variant])
                staged_paths.append(path)
            _write_yaml(staging / "strategy_spec.yaml", attempt_spec)
            preflight_paths = staged_paths
            if target_scoped:
                preflight_paths = [
                    path for path in staged_paths
                    if path.parent.name == certification_target_variant
                ]
            preflight = run_preflight(
                config_paths=preflight_paths,
                run_tests=False,
                project_root=self.project_root,
            )
            if not bool(preflight.get("passed")):
                failures = "; ".join(str(item) for item in preflight.get("failures") or [])
                raise ValueError(f"follow-up preflight failed before installation: {failures}")
            config_hashes = {variant: _file_sha256(path) for variant, path in zip(variants, staged_paths)}
            dataset_bindings = {
                variant: {
                    "dataset_id": dataset_manifests[variant].dataset_id,
                    "dataset_manifest_sha256": _file_sha256(
                        self.layout.dataset_root
                        / dataset_manifests[variant].dataset_id
                        / "dataset_manifest.json"
                    ),
                }
                for variant in variants
            }
            manifest = {
                "schema": FOLLOW_UP_SCHEMA,
                "campaign_id": parsed.campaign_id,
                "attempt_id": attempt_id,
                "attempt_kind": parsed.attempt_kind,
                "attempt_provenance": "authored",
                "parent_attempt_id": parsed.parent_attempt_id,
                "target_variant_id": parsed.target_variant_id,
                "reason": parsed.reason,
                "created_by": parsed.created_by,
                "authorized_by": parsed.authorized_by,
                "created_at": created_at.isoformat(),
                "variant_order": list(variants),
                "source_config_sha256": source_hashes,
                "config_sha256": config_hashes,
                "variant_mechanic_signatures": {
                    variant: str((configs[variant].get("research_metadata") or {}).get("mechanic_signature") or "")
                    for variant in variants
                },
                "dataset_bindings": dataset_bindings,
                "changes": changes,
                "preflight": {
                    "verdict": "PASS",
                    "config_count": len(preflight_paths),
                    "warnings": [str(item) for item in preflight.get("warnings") or []],
                },
                "immutable": True,
                "automatic_replay_permitted": False,
                "ledger_event_stage": f"follow_up_attempt/{attempt_id}",
            }
            if (
                parsed.attempt_kind == "pre_pnl_protocol_declaration"
                and parsed.target_variant_id is not None
            ):
                manifest["research_objectives_sha256"] = configs[
                    parsed.target_variant_id
                ].get("research_objectives_sha256")
                destination_hash = configs[parsed.target_variant_id].get(
                    "destination_benchmark_contract_sha256"
                )
                if destination_hash:
                    manifest["destination_benchmark_contract_sha256"] = (
                        destination_hash
                    )
            unique_dataset_ids = {
                binding["dataset_id"] for binding in dataset_bindings.values()
            }
            if len(unique_dataset_ids) == 1:
                dataset_id = next(iter(unique_dataset_ids))
                manifest["dataset_id"] = dataset_id
                manifest["dataset_manifest_sha256"] = dataset_bindings[
                    next(iter(dataset_bindings))
                ]["dataset_manifest_sha256"]
            _write_json(staging / "attempt_manifest.json", manifest)
            if destination.exists() or destination.is_symlink():
                raise FileExistsError(f"follow-up attempt identity already exists: {destination}")
            os.replace(staging, destination)
            installed = True
        except Exception:
            if not installed:
                shutil.rmtree(staging, ignore_errors=True)
            raise

        final_paths = tuple(destination / variant / "config.yaml" for variant in variants)
        ledger_path = self.project_root / "research_ledger.csv"
        ledger_before = ledger_path.read_bytes() if ledger_path.is_file() else None
        try:
            ledger_rows, _ = append_planned_follow_up(
                campaign=campaign,
                attempt_id=attempt_id,
                attempt_kind=parsed.attempt_kind,
                parent_attempt_id=parsed.parent_attempt_id,
                reason=parsed.reason,
                dataset_ids={
                    variant: dataset_manifests[variant].dataset_id
                    for variant in variants
                },
                config_paths={
                    variant: _display_path(path, self.project_root) for variant, path in zip(variants, final_paths)
                },
                project_root=self.project_root,
            )
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            _restore_bytes(ledger_path, ledger_before)
            raise

        try:
            write_definition_manifests(
                self.layout.active_campaign_root,
                project_root=self.project_root,
                apply=True,
            )
            refresh = refresh_generated_indexes_if_stale(self.project_root)
        except Exception:
            # Source lineage is authoritative and safely installed.  Generated
            # indexes are rebuildable; never delete an already issued attempt
            # identity merely because a derived view refresh failed.
            refresh = {"refreshed": False}

        return FollowUpAttemptResult(
            campaign_id=parsed.campaign_id,
            attempt_id=attempt_id,
            attempt_kind=parsed.attempt_kind,
            parent_attempt_id=parsed.parent_attempt_id,
            destination=destination,
            manifest_path=destination / "attempt_manifest.json",
            config_paths=final_paths,
            config_sha256={variant: _file_sha256(path) for variant, path in zip(variants, final_paths)},
            ledger_rows_appended=ledger_rows,
            indexes_refreshed=bool(refresh.get("refreshed")),
        )

    def list_attempts(
        self,
        campaign_id: str,
        *,
        include_dataset_bindings: bool = True,
    ) -> list[dict[str, Any]]:
        campaign_root, _campaign, _variants = self._campaign(campaign_id)
        original = {
            "attempt_id": "original",
            "attempt_kind": "original",
            "parent_attempt_id": None,
            "reason": "Frozen original Studio publication.",
        }
        rows: list[dict[str, Any]] = []
        root = campaign_root / FOLLOW_UP_ROOT
        for path in sorted(root.glob("*/attempt_manifest.json")) if root.is_dir() else []:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(value, dict) and value.get("schema") == FOLLOW_UP_SCHEMA:
                rows.append(
                    {
                        "attempt_id": value.get("attempt_id"),
                        "attempt_kind": value.get("attempt_kind"),
                        "parent_attempt_id": value.get("parent_attempt_id"),
                        "reason": value.get("reason"),
                        "created_at": value.get("created_at"),
                        "target_variant_id": value.get("target_variant_id"),
                    }
                )
        attempts = [
            original,
            *sorted(
                rows,
                key=lambda item: (
                    str(item.get("created_at") or ""),
                    str(item["attempt_id"]),
                ),
            ),
        ]
        if not include_dataset_bindings:
            return attempts
        bindings_by_attempt: dict[str, list[dict[str, Any]]] = {}
        for attempt in attempts:
            attempt_id = str(attempt.get("attempt_id") or "")
            try:
                bindings = self._attempt_dataset_bindings(campaign_id, attempt_id)
            except (FileNotFoundError, KeyError, OSError, ValueError) as exc:
                attempt["dataset_lineage_error"] = str(exc)
                bindings = []
            bindings_by_attempt[attempt_id] = bindings
            attempt["dataset_bindings"] = bindings

        for attempt in attempts:
            attempt_id = str(attempt.get("attempt_id") or "")
            parent_id = attempt.get("parent_attempt_id")
            parent_bindings = {
                str(item.get("variant_id") or ""): item
                for item in bindings_by_attempt.get(str(parent_id or ""), [])
            }
            for binding in bindings_by_attempt.get(attempt_id, []):
                if attempt_id == "original":
                    binding["dataset_change"] = "original"
                    binding["parent_dataset_id"] = None
                    continue
                parent = parent_bindings.get(str(binding.get("variant_id") or ""))
                if parent is None:
                    binding["dataset_change"] = "unknown"
                    binding["parent_dataset_id"] = None
                    continue
                binding["parent_dataset_id"] = parent.get("dataset_id")
                identity = (
                    binding.get("dataset_id"),
                    binding.get("source_sha256"),
                )
                parent_identity = (
                    parent.get("dataset_id"),
                    parent.get("source_sha256"),
                )
                binding["dataset_change"] = (
                    "inherited" if identity == parent_identity else "changed"
                )
        return attempts

    def attempt_detail(
        self,
        campaign_id: str,
        attempt_id: str,
    ) -> dict[str, Any]:
        """Load dataset lineage for one immutable attempt on demand."""

        attempts = self.list_attempts(
            campaign_id,
            include_dataset_bindings=False,
        )
        attempt = next(
            (
                dict(item)
                for item in attempts
                if str(item.get("attempt_id") or "") == attempt_id
            ),
            None,
        )
        if attempt is None:
            raise FileNotFoundError(
                f"immutable attempt not found: {campaign_id}/{attempt_id}"
            )
        try:
            bindings = self._attempt_dataset_bindings(campaign_id, attempt_id)
        except (FileNotFoundError, KeyError, OSError, ValueError) as exc:
            attempt["dataset_lineage_error"] = str(exc)
            bindings = []
        parent_id = str(attempt.get("parent_attempt_id") or "")
        parent_bindings: dict[str, dict[str, Any]] = {}
        if parent_id:
            try:
                parent_bindings = {
                    str(item.get("variant_id") or ""): item
                    for item in self._attempt_dataset_bindings(
                        campaign_id,
                        parent_id,
                    )
                }
            except (FileNotFoundError, KeyError, OSError, ValueError):
                parent_bindings = {}
        for binding in bindings:
            if attempt_id == "original":
                binding["dataset_change"] = "original"
                binding["parent_dataset_id"] = None
                continue
            parent = parent_bindings.get(str(binding.get("variant_id") or ""))
            binding["parent_dataset_id"] = (
                parent.get("dataset_id") if parent else None
            )
            if parent is None:
                binding["dataset_change"] = "unknown"
            else:
                binding["dataset_change"] = (
                    "inherited"
                    if (
                        binding.get("dataset_id"),
                        binding.get("source_sha256"),
                    )
                    == (
                        parent.get("dataset_id"),
                        parent.get("source_sha256"),
                    )
                    else "changed"
                )
        attempt["dataset_bindings"] = bindings
        return attempt

    def _attempt_dataset_bindings(
        self,
        campaign_id: str,
        attempt_id: str,
    ) -> list[dict[str, Any]]:
        bindings: list[dict[str, Any]] = []
        for config_path in self.config_paths(campaign_id, attempt_id):
            cfg = _read_yaml(config_path)
            data = cfg.get("data") if isinstance(cfg.get("data"), Mapping) else {}
            dataset_id = str(cfg.get("dataset_id") or data.get("dataset_id") or "")
            if not dataset_id:
                raise ValueError(f"{config_path.parent.name} does not declare a governed dataset_id")
            manifest_path = self.layout.dataset_root / dataset_id / "dataset_manifest.json"
            if not manifest_path.is_file():
                raise FileNotFoundError(
                    f"governed dataset manifest is missing for {config_path.parent.name}: "
                    f"{manifest_path}"
                )
            manifest = _read_json(manifest_path)
            if str(manifest.get("dataset_id") or "") != dataset_id:
                raise ValueError(f"governed dataset manifest identity mismatch: {manifest_path}")
            event_source = (
                manifest.get("event_source")
                if isinstance(manifest.get("event_source"), Mapping)
                else {}
            )
            gate = inspect_validation_gate(cfg, config_path)
            input_data_hash = str(gate.get("input_data_hash") or "")
            binding = {
                "variant_id": str(cfg.get("variant_id") or config_path.parent.name),
                "dataset_id": dataset_id,
                "source_type": str(event_source.get("source") or manifest.get("source") or ""),
                "bar_source_type": str(manifest.get("source") or ""),
                "coverage_start": manifest.get("coverage_start"),
                "coverage_end": manifest.get("coverage_end"),
                "quality_verdict": manifest.get("quality_verdict"),
                "source_sha256": manifest.get("source_sha256")
                or data.get("source_sha256"),
                "input_data_hash": input_data_hash or None,
                "manifest_path": str(manifest_path),
                "test_data_windows": _attempt_test_data_windows(
                    cfg,
                    project_root=self.project_root,
                    evidence_root=self.layout.evidence_roots[0],
                ),
            }
            if not input_data_hash:
                binding["input_data_hash_error"] = "; ".join(
                    str(item) for item in gate.get("errors") or []
                ) or "current input-data hash could not be computed"
            bindings.append(binding)
        return bindings

    def config_paths(self, campaign_id: str, attempt_id: str = "original") -> tuple[Path, ...]:
        campaign_root, _campaign, variants = self._campaign(campaign_id)
        declared_hashes: Mapping[str, Any] | None = None
        if attempt_id == "original":
            paths = tuple(campaign_root / "variants" / variant / "config.yaml" for variant in variants)
        else:
            if re.fullmatch(r"[a-z0-9][a-z0-9_]*", attempt_id) is None:
                raise ValueError("attempt_id must use lowercase letters, numbers, and underscores")
            attempt_root = campaign_root / FOLLOW_UP_ROOT / attempt_id
            manifest_path = attempt_root / "attempt_manifest.json"
            if not manifest_path.is_file():
                raise FileNotFoundError(f"governed follow-up manifest is missing: {manifest_path}")
            manifest = _read_json(manifest_path)
            if manifest.get("schema") != FOLLOW_UP_SCHEMA or manifest.get("attempt_id") != attempt_id:
                raise ValueError(f"follow-up manifest identity is invalid: {manifest_path}")
            declared_hashes = manifest.get("config_sha256")
            frozen_order = manifest.get("variant_order")
            if frozen_order is None and isinstance(declared_hashes, Mapping):
                # Backward-compatible immutable attempts predate the explicit
                # variant_order field. Their ordered hash-map keys are the
                # only configs that attempt can legitimately contain.
                frozen_order = list(declared_hashes)
            if (
                not isinstance(frozen_order, list)
                or not frozen_order
                or any(
                    not isinstance(variant, str)
                    or re.fullmatch(r"[a-z0-9][a-z0-9_]*", variant) is None
                    for variant in frozen_order
                )
                or len(set(frozen_order)) != len(frozen_order)
            ):
                raise ValueError(
                    f"follow-up manifest variant_order is missing or invalid: {manifest_path}"
                )
            # A follow-up is immutable evidence about the campaign variants
            # that existed when it was authored. Later sequential variants
            # must not retroactively become required files in an older
            # attempt.
            variants = tuple(frozen_order)
            if not isinstance(declared_hashes, Mapping) or set(declared_hashes) != set(variants):
                raise ValueError(f"follow-up manifest does not hash every declared config: {manifest_path}")
            paths = tuple(attempt_root / variant / "config.yaml" for variant in variants)
        missing = [str(path) for path in paths if not path.is_file()]
        if missing:
            raise FileNotFoundError("attempt does not contain every frozen config: " + ", ".join(missing))
        for variant, path in zip(variants, paths):
            cfg = _read_yaml(path)
            if cfg.get("campaign_id") != campaign_id or cfg.get("variant_id") != variant:
                raise ValueError(f"attempt config identity mismatch: {path}")
            if str(cfg.get("attempt_id") or "") != attempt_id:
                raise ValueError(f"attempt config lineage mismatch: {path}")
            if declared_hashes is not None and str(declared_hashes.get(variant) or "") != _file_sha256(path):
                raise ValueError(
                    f"immutable follow-up config hash drift for {variant}; create a new explicit attempt "
                    "instead of editing the published definition"
                )
        return paths

    def target_config_path(self, campaign_id: str, attempt_id: str = "original") -> Path:
        """Resolve the sole variant governed for execution by an attempt.

        Campaign order is historical context, not cross-variant execution
        lineage. Sibling configs may remain in an immutable campaign snapshot,
        but they cannot qualify, approve, preflight, or block the target.
        """

        paths = self.config_paths(campaign_id, attempt_id)
        target_variant = ""
        if attempt_id != "original":
            campaign_root, _campaign, _variants = self._campaign(campaign_id)
            manifest = _read_json(
                campaign_root / FOLLOW_UP_ROOT / attempt_id / "attempt_manifest.json"
            )
            target_variant = str(manifest.get("target_variant_id") or "")
        if not target_variant:
            target_variant = paths[-1].parent.name
        matches = [path for path in paths if path.parent.name == target_variant]
        if len(matches) != 1:
            raise ValueError(
                f"attempt {attempt_id!r} must contain exactly one target config for "
                f"{target_variant}; found {len(matches)}"
            )
        return matches[0]

    def queue_mechanics_validation(
        self,
        campaign_id: str,
        attempt_id: str,
    ) -> list[JobRecordV1]:
        from alphaquest.studio.worker import MECHANICS_VALIDATION_RUN

        paths = (self.target_config_path(campaign_id, attempt_id),)
        queue = SQLiteJobQueue(self.layout.studio_runtime_root / "jobs.sqlite3")
        jobs: list[JobRecordV1] = []
        for config_path in paths:
            cfg = _read_yaml(config_path)
            gate = inspect_validation_gate(cfg, config_path)
            config_hash = str(gate.get("config_hash") or "")
            data_hash = str(gate.get("input_data_hash") or "")
            if gate.get("required") is not True or not config_hash or not data_hash:
                errors = "; ".join(str(item) for item in gate.get("errors") or [])
                raise ValueError(f"mechanics hashes are unresolved for {config_path.parent.name}: {errors}")
            base_idempotency_key = (
                f"{campaign_id}:{cfg['variant_id']}:{attempt_id}:mechanics_validation:"
                f"{config_hash}:{data_hash}"
            )
            matching_jobs = [
                prior
                for prior in queue.list_jobs(limit=10_000)
                if prior.job_type == MECHANICS_VALIDATION_RUN
                and prior.campaign_id == campaign_id
                and str(prior.payload.get("attempt_id") or "") == attempt_id
                and str(prior.payload.get("variant_id") or "")
                == str(cfg["variant_id"])
                and prior.hash_locks
                == {"config_hash": config_hash, "input_data_hash": data_hash}
                and (
                    prior.idempotency_key == base_idempotency_key
                    or prior.idempotency_key.startswith(
                        f"{base_idempotency_key}:retry:"
                    )
                )
            ]
            latest = matching_jobs[0] if matching_jobs else None
            if latest is not None and latest.state not in {
                OperationalState.FAILED_OPERATIONAL,
                OperationalState.CANCELLED,
            }:
                jobs.append(latest)
                continue
            failed_attempts = [
                prior
                for prior in matching_jobs
                if prior.state
                in {OperationalState.FAILED_OPERATIONAL, OperationalState.CANCELLED}
            ]
            if len(failed_attempts) >= 3:
                raise ValueError(
                    "mechanics evidence reached its three-attempt operational retry limit; "
                    "inspect the preserved failures before creating another governed follow-up"
                )
            idempotency_key = (
                f"{base_idempotency_key}:retry:{len(failed_attempts)}"
                if latest is not None
                else base_idempotency_key
            )
            payload = {
                "campaign_id": campaign_id,
                "variant_id": str(cfg["variant_id"]),
                "attempt_id": attempt_id,
                "config_path": str(config_path),
            }
            if latest is not None:
                payload["retry_of_job_id"] = latest.job_id
            archived_run = (
                self._archive_failed_mechanics_run(
                    cfg,
                    source_config_path=config_path,
                    failed_job_ids=[prior.job_id for prior in failed_attempts],
                )
                if latest is not None
                else None
            )
            try:
                submitted = queue.submit(
                    job_type=MECHANICS_VALIDATION_RUN,
                    campaign_id=campaign_id,
                    payload=payload,
                    idempotency_key=idempotency_key,
                    hash_locks={"config_hash": config_hash, "input_data_hash": data_hash},
                )
            except Exception:
                if archived_run is not None:
                    source, archive = archived_run
                    source.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(archive, source)
                raise
            jobs.append(submitted)
        return jobs

    def _archive_failed_mechanics_run(
        self,
        cfg: dict[str, Any],
        *,
        source_config_path: Path,
        failed_job_ids: list[str],
    ) -> tuple[Path, Path] | None:
        """Preserve an incomplete run root before an explicit operational retry."""

        from alphaquest.run_core import _apply_mechanics_validation_contract

        generated = deepcopy(cfg)
        _apply_mechanics_validation_contract(generated)
        run_root = (
            self.layout.evidence_roots[0]
            / str(generated["campaign_id"])
            / str(generated["variant_id"])
            / str(generated["symbol"])
            / str(generated["test_run_id"])
        )
        if not run_root.exists():
            return None
        archive_root = (
            self.layout.studio_runtime_root
            / "failed-mechanics-runs"
            / failed_job_ids[-1]
        )
        archive = archive_root / run_root.name
        if archive.exists() or archive.is_symlink():
            raise FileExistsError(
                f"failed mechanics-run archive already exists: {archive}"
            )
        archive_root.mkdir(parents=True, exist_ok=False)
        os.replace(run_root, archive)
        _write_json(
            archive_root / "recovery.json",
            {
                "schema": "alphaquest.failed-mechanics-run-recovery/v1",
                "failed_job_ids": failed_job_ids,
                "source_config_path": str(source_config_path),
                "source_run_root": str(run_root),
                "archived_run_root": str(archive),
                "reason": (
                    "Preserved incomplete generated-validation evidence before "
                    "an explicit hash-identical operational retry."
                ),
            },
        )
        return run_root, archive

    def queue_performance(self, campaign_id: str, attempt_id: str) -> list[JobRecordV1]:
        paths = (self.target_config_path(campaign_id, attempt_id),)
        approvals = require_all_variant_mechanics_approved(list(paths))
        gates = {Path(str(item["config_path"])).resolve(): item for item in approvals}
        queue = SQLiteJobQueue(self.layout.studio_runtime_root / "jobs.sqlite3")
        jobs: list[JobRecordV1] = []
        for config_path in paths:
            cfg = _read_yaml(config_path)
            gate = gates[config_path.resolve()]
            prior_jobs = [
                prior
                for prior in queue.list_jobs(limit=10_000)
                if prior.job_type == "campaign_variant_run"
                and prior.campaign_id == campaign_id
                and str(prior.payload.get("attempt_id") or "") == attempt_id
                and str(prior.payload.get("variant_id") or "")
                == str(cfg["variant_id"])
            ]
            for prior in prior_jobs:
                if prior.state in {
                    OperationalState.QUEUED,
                    OperationalState.RUNNING,
                    OperationalState.CANCEL_REQUESTED,
                }:
                    return [prior]
            output_dir = (
                self.layout.evidence_roots[0]
                / campaign_id
                / str(cfg["variant_id"])
                / str(cfg.get("symbol") or (cfg.get("data") or {}).get("symbol"))
                / str(cfg["test_run_id"])
            )
            terminal = [
                prior
                for prior in prior_jobs
                if not _is_legacy_unreserved_preflight_only_job(prior)
                and not (
                    prior.payload.get("pre_performance_retry") is not None
                    and not prior.attempt_reserved
                    and prior.state
                    in {
                        OperationalState.BLOCKED,
                        OperationalState.FAILED_OPERATIONAL,
                    }
                )
            ]
            abandoned_retry_submissions = [
                prior
                for prior in prior_jobs
                if prior.payload.get("pre_performance_retry") is not None
                and not prior.attempt_reserved
                and prior.state
                in {
                    OperationalState.BLOCKED,
                    OperationalState.FAILED_OPERATIONAL,
                }
            ]
            if len(abandoned_retry_submissions) > 2:
                raise ValueError(
                    "Pre-performance retry submission blocked after three audited "
                    "pre-reservation submission failures"
                )
            retry_contract: dict[str, Any] | None = None
            if terminal:
                if len(terminal) != 1:
                    _require_queueable_performance_job(
                        terminal[0],
                        attempt_id=attempt_id,
                    )
                failed = terminal[0]
                retry_contract = self._archive_preperformance_campaign_run(
                    failed,
                    config_path=config_path,
                    cfg=cfg,
                    gate=gate,
                    output_dir=output_dir,
                )
                for abandoned in abandoned_retry_submissions:
                    prior_contract = abandoned.payload.get("pre_performance_retry")
                    if not isinstance(prior_contract, Mapping) or any(
                        str(prior_contract.get(key) or "")
                        != str(retry_contract.get(key) or "")
                        for key in (
                            "failed_job_id",
                            "recovery_path",
                            "proof_sha256",
                            "prior_resolution_sha256",
                        )
                    ):
                        raise ValueError(
                            "Pre-performance retry submission proof has changed since "
                            "the prior pre-reservation failure"
                        )
            base_idempotency_key = (
                f"{campaign_id}:{cfg['variant_id']}:{attempt_id}:"
                f"{TARGET_VARIANT_PERFORMANCE_SCOPE}"
            )
            payload = {
                "campaign_id": campaign_id,
                "variant_id": str(cfg["variant_id"]),
                "attempt_id": attempt_id,
                "execution_scope": TARGET_VARIANT_PERFORMANCE_SCOPE,
                "config_path": str(config_path),
                "output_dir": str(output_dir),
            }
            hash_locks = _performance_hash_locks(gate)
            idempotency_key = base_idempotency_key
            if retry_contract is not None:
                payload["pre_performance_retry"] = retry_contract
                payload["retry_of_job_id"] = retry_contract["failed_job_id"]
                idempotency_key = f"{base_idempotency_key}:retry:1"
                if abandoned_retry_submissions:
                    idempotency_key += (
                        f":submission:{len(abandoned_retry_submissions) + 1}"
                    )
                hash_locks["pre_performance_proof_sha256"] = str(
                    retry_contract["proof_sha256"]
                )
            job = queue.submit(
                job_type="campaign_variant_run",
                campaign_id=campaign_id,
                payload=payload,
                idempotency_key=idempotency_key,
                hash_locks=hash_locks,
            )
            _require_queueable_performance_job(job, attempt_id=attempt_id)
            jobs.append(job)
        return jobs

    def _archive_preperformance_campaign_run(
        self,
        failed: JobRecordV1,
        *,
        config_path: Path,
        cfg: Mapping[str, Any],
        gate: Mapping[str, Any],
        output_dir: Path,
    ) -> dict[str, Any]:
        """Preserve a zero-PnL failed run before one explicit continuation."""

        attempt_id = str(cfg.get("attempt_id") or "")
        variant_id = str(cfg.get("variant_id") or "")
        campaign_id = str(cfg.get("campaign_id") or "")
        if (
            failed.state not in {OperationalState.FAILED_OPERATIONAL, OperationalState.CANCELLED}
            or not failed.attempt_reserved
            or failed.payload.get("pre_performance_retry") is not None
            or str(failed.payload.get("config_path") or "") != str(config_path)
            or Path(str(failed.payload.get("output_dir") or "")).resolve()
            != output_dir.resolve()
        ):
            _require_queueable_performance_job(failed, attempt_id=attempt_id)
        if failed.hash_locks.get("config_hash") != str(gate.get("config_hash") or ""):
            raise ValueError("Pre-performance retry blocked: failed job config hash has drifted")
        if failed.hash_locks.get("input_data_hash") != str(gate.get("input_data_hash") or ""):
            raise ValueError("Pre-performance retry blocked: failed job input hash has drifted")

        registry = ExperimentRegistry(
            self.layout.research_artifact_root / "governance/experiment_registry.jsonl"
        )
        if registry.current_status(campaign_id, variant_id, attempt_id) != "FAILED":
            raise ValueError(
                "Pre-performance retry requires a terminal FAILED experiment reservation"
            )
        resolution = registry.current_resolution_event(campaign_id, variant_id, attempt_id)
        if not isinstance(resolution, Mapping) or resolution.get("result_sha256") is not None:
            raise ValueError(
                "Pre-performance retry requires an unbound operational failure resolution"
            )
        prior_resolution_sha256 = str(resolution.get("record_sha256") or "")

        archive_root = (
            self.layout.studio_runtime_root / "failed-campaign-runs" / failed.job_id
        )
        archive = archive_root / output_dir.name
        recovery_path = archive_root / "recovery.json"
        if recovery_path.is_file():
            recovery = _read_json(recovery_path)
        else:
            if not _is_proven_pre_performance_incomplete_run(output_dir, attempt_id):
                _require_queueable_performance_job(failed, attempt_id=attempt_id)
            approval_path = Path(str(gate.get("approval_path") or ""))
            if not approval_path.is_file():
                raise ValueError("Pre-performance retry requires the current approval artifact")
            files = {
                path.relative_to(output_dir).as_posix(): _file_sha256(path)
                for path in sorted(output_dir.rglob("*"))
                if path.is_file()
            }
            recovery = {
                "schema": "alphaquest.pre-performance-campaign-retry/v1",
                "campaign_id": campaign_id,
                "variant_id": variant_id,
                "attempt_id": attempt_id,
                "retry_index": 1,
                "failed_job_id": failed.job_id,
                "source_config_path": str(config_path),
                "source_run_root": str(output_dir),
                "archived_run_root": str(archive),
                "source_file_sha256": files,
                "config_hash": str(gate.get("config_hash") or ""),
                "input_data_hash": str(gate.get("input_data_hash") or ""),
                "approval_path": str(approval_path),
                "approval_sha256": _file_sha256(approval_path),
                "strategy_implementation_sha256": str(
                    gate.get("strategy_implementation_sha256") or ""
                ),
                "strategy_certification_manifest_sha256": str(
                    gate.get("strategy_certification_manifest_sha256") or ""
                ),
                "prior_resolution_sha256": prior_resolution_sha256,
                "reason": (
                    "Explicit user-authorized continuation after preserved evidence proved "
                    "that no PnL-bearing campaign stage began."
                ),
            }
            archive_root.mkdir(parents=True, exist_ok=False)
            _write_json(recovery_path, recovery)
        if str(recovery.get("failed_job_id") or "") != failed.job_id:
            raise ValueError("Pre-performance retry recovery belongs to a different failed job")
        if str(recovery.get("prior_resolution_sha256") or "") != prior_resolution_sha256:
            raise ValueError("Pre-performance retry recovery resolution hash has drifted")
        if output_dir.exists() and not archive.exists():
            os.replace(output_dir, archive)
        if output_dir.exists() or not archive.is_dir():
            raise ValueError("Pre-performance retry could not preserve the incomplete run root")
        recorded_files = recovery.get("source_file_sha256")
        if not isinstance(recorded_files, Mapping) or any(
            not (archive / str(relative)).is_file()
            or _file_sha256(archive / str(relative)) != str(expected)
            for relative, expected in recorded_files.items()
        ):
            raise ValueError("Pre-performance retry archived evidence hash mismatch")
        return {
            "schema": str(recovery["schema"]),
            "retry_index": 1,
            "failed_job_id": failed.job_id,
            "recovery_path": str(recovery_path),
            "proof_sha256": _file_sha256(recovery_path),
            "prior_resolution_sha256": prior_resolution_sha256,
        }

    def _campaign(self, campaign_id: str) -> tuple[Path, dict[str, Any], tuple[str, ...]]:
        if re.fullmatch(r"[a-z0-9][a-z0-9_]*", campaign_id) is None:
            raise ValueError("campaign_id must use lowercase letters, numbers, and underscores")
        campaign_root = self.layout.active_campaign_root / campaign_id
        campaign_path = campaign_root / "campaign.yaml"
        if not campaign_path.is_file():
            raise FileNotFoundError(f"active governed campaign is missing: {campaign_path}")
        campaign = _read_yaml(campaign_path)
        declared = campaign.get("variants")
        if not isinstance(declared, list) or not 1 <= len(declared) <= 5:
            raise ValueError("Studio follow-up attempts require one to five declared campaign variants")
        variants = tuple(
            str(item if isinstance(item, str) else (item or {}).get("variant_id") or (item or {}).get("id") or "")
            for item in declared
        )
        if any(not item for item in variants) or len(set(variants)) != len(variants):
            raise ValueError("campaign.yaml must declare unique variant IDs")
        return campaign_root, campaign, variants

    def _require_studio_authored(
        self,
        campaign_root: Path,
        campaign: Mapping[str, Any],
        variants: tuple[str, ...],
    ) -> None:
        manifest = campaign_root / "authoring_manifest.json"
        spec = campaign_root / "strategy_spec.yaml"
        if not manifest.is_file() or not spec.is_file():
            raise ValueError(
                "follow-up authoring is available only for complete Studio publications; "
                "unfinished or developer-managed campaigns remain blocked"
            )
        document = _read_json(manifest)
        campaign_id = str(campaign.get("campaign_id") or "")
        if document.get("schema") != AUTHORING_MANIFEST_SCHEMA:
            raise ValueError("Studio authoring manifest schema is missing or unsupported")
        if document.get("campaign_id") != campaign_id or document.get("variant_count") != len(variants):
            raise ValueError("Studio authoring manifest identity does not match the active campaign")

        expected_paths = {
            "campaign.yaml",
            "strategy_spec.yaml",
            *(f"variants/{variant}/config.yaml" for variant in variants),
        }
        hashes = document.get("compiled_document_sha256")
        if not isinstance(hashes, Mapping) or set(hashes) != expected_paths:
            raise ValueError("Studio authoring manifest must hash the campaign, strategy spec, and declared configs")
        for relative in sorted(expected_paths):
            path = campaign_root / relative
            if not path.is_file():
                raise FileNotFoundError(f"Studio compiled source document is missing: {path}")
            actual = _object_sha256(_read_yaml(path))
            if str(hashes.get(relative) or "") != actual:
                raise ValueError(
                    f"immutable original compiled source hash drift for {relative}; "
                    "restore the reviewed publication before creating a follow-up"
                )

        spec_document = _read_yaml(spec)
        if (
            spec_document.get("schema") != STRATEGY_SPEC_SCHEMA
            or spec_document.get("campaign_id") != campaign_id
            or spec_document.get("frozen") is not True
        ):
            raise ValueError("reviewed strategy_spec.yaml identity is invalid or is not frozen")
        declared_signatures = document.get("variant_mechanic_signatures")
        if not isinstance(declared_signatures, Mapping) or set(declared_signatures) != set(variants):
            raise ValueError("Studio authoring manifest must bind every variant mechanic signature")
        spec_variants = spec_document.get("variants")
        if not isinstance(spec_variants, list) or len(spec_variants) != len(variants):
            raise ValueError("reviewed strategy_spec.yaml must contain every declared variant")
        spec_by_variant = {
            str(item.get("variant_id") or ""): item for item in spec_variants if isinstance(item, Mapping)
        }
        if set(spec_by_variant) != set(variants):
            raise ValueError("reviewed strategy_spec.yaml variant identity does not match campaign.yaml")
        computed_signatures: dict[str, str] = {}
        for variant in variants:
            cfg = _read_yaml(campaign_root / "variants" / variant / "config.yaml")
            computed = _config_mechanic_signature(cfg)
            stored = str((cfg.get("research_metadata") or {}).get("mechanic_signature") or "")
            declared = str(declared_signatures.get(variant) or "")
            spec_signature = str(spec_by_variant[variant].get("mechanic_signature") or "")
            if not stored or len({computed, stored, declared, spec_signature}) != 1:
                raise ValueError(f"original mechanic signature identity mismatch for {variant}")
            computed_signatures[variant] = computed
        _require_unique_mechanic_signatures(computed_signatures)

    def _new_attempt_id(self, kind: str, campaign_root: Path) -> str:
        timestamp = self._now().astimezone(UTC).strftime("%Y%m%dt%H%M%S")
        token = re.sub(r"[^a-z0-9]", "", self._token().lower())[:12]
        if not token:
            raise ValueError("attempt token generator did not return a usable identity")
        attempt_id = f"{kind}_{timestamp}_{token}"
        if (campaign_root / FOLLOW_UP_ROOT / attempt_id).exists():
            raise FileExistsError(f"generated follow-up identity already exists: {attempt_id}")
        return attempt_id

    def _require_kind_policy(
        self,
        request: FollowUpAttemptRequestV1,
        campaign_root: Path,
        campaign: Mapping[str, Any],
        parent_configs: Mapping[str, Mapping[str, Any]],
        parent_paths: Mapping[str, Path],
    ) -> None:
        if request.attempt_kind in {
            "pre_pnl_protocol_declaration",
            "pre_pnl_mechanics_correction",
            "pre_pnl_parameter_declaration",
        }:
            if _attempt_has_performance_evidence(
                self.layout.evidence_roots,
                self.layout.studio_runtime_root,
                self.project_root,
                request.campaign_id,
                request.parent_attempt_id,
                parent_configs,
                parent_paths,
            ):
                raise ValueError(
                    f"{request.attempt_kind} is forbidden after performance evidence exists; "
                    "use replication, data refresh, methodology rerun, or an authorized rescue"
                )
        if request.attempt_kind == "pre_pnl_protocol_declaration":
            assert request.target_variant_id is not None
            parent = parent_configs.get(request.target_variant_id)
            if parent is None:
                raise ValueError(
                    f"unknown pre-PnL protocol target variant: {request.target_variant_id}"
                )
            has_objectives = isinstance(parent.get("research_objectives"), Mapping)
            has_objectives_hash = bool(parent.get("research_objectives_sha256"))
            if has_objectives or has_objectives_hash:
                raise ValueError(
                    "the selected parent already has a frozen research-objective contract; "
                    "use another governed follow-up type"
                )
        if request.attempt_kind != "rescue":
            return
        policy = campaign.get("rescue_policy")
        if not isinstance(policy, Mapping) or policy.get("allowed") is not True:
            raise ValueError("campaign rescue_policy does not authorize rescue attempts")
        maximum = policy.get("max_rescues_per_failed_variant")
        if not isinstance(maximum, int) or maximum < 1 or maximum > 1:
            raise ValueError("campaign rescue policy must explicitly allow at most one rescue per failed variant")
        assert request.target_variant_id is not None
        if request.target_variant_id not in parent_configs:
            raise ValueError(f"unknown rescue target variant: {request.target_variant_id}")
        if not _attempt_variant_failed(
            self.layout.evidence_roots,
            request.campaign_id,
            request.target_variant_id,
            request.parent_attempt_id,
            parent_configs[request.target_variant_id],
            parent_paths[request.target_variant_id],
        ):
            raise ValueError(
                "authorized rescue requires a complete, hash-valid finalized FAIL for the target parent attempt"
            )
        existing_attempts: set[str] = set()
        for path in campaign_root.rglob("config.yaml"):
            cfg = _read_yaml(path)
            research = cfg.get("research_metadata") if isinstance(cfg.get("research_metadata"), dict) else {}
            if (
                cfg.get("attempt_kind") == "rescue"
                and (research.get("rescue_target_variant_id") or research.get("parent_variant_id"))
                == request.target_variant_id
            ):
                existing_attempts.add(str(cfg.get("attempt_id") or path.parent))
        if len(existing_attempts) >= maximum:
            raise ValueError(f"variant {request.target_variant_id} already has its one authorized rescue attempt")

    def _load_dataset(self, dataset_id: str) -> DatasetManifestV1:
        path = self.layout.dataset_root / dataset_id / "dataset_manifest.json"
        if not path.is_file():
            raise FileNotFoundError(f"governed dataset manifest is missing: {path}")
        manifest = DatasetManifestV1.model_validate(_read_json(path))
        if manifest.dataset_id != dataset_id:
            raise ValueError("governed dataset manifest ID does not match its source directory")
        if manifest.quality_verdict != "PASS":
            raise ValueError("data refresh requires a governed dataset with quality verdict PASS")
        if manifest.timestamp_semantics != "bar_open":
            raise ValueError("data refresh requires canonical bar-open timestamps")
        canonical = _resolve_project_owned_path(manifest.path, self.project_root)
        if not canonical.is_file() or _file_sha256(canonical) != manifest.canonical_sha256:
            raise ValueError("governed dataset canonical file is missing or hash-drifted")
        if manifest.source_sha256 != manifest.canonical_sha256:
            attachments = self.layout.studio_runtime_root / "raw-attachments" / dataset_id
            source_verified = (
                any(
                    item.is_file() and _file_sha256(item) == manifest.source_sha256 for item in attachments.glob("**/*")
                )
                if attachments.is_dir()
                else False
            )
            if not source_verified:
                raise ValueError("governed dataset quarantined source is missing or hash-drifted")
        if manifest.roll_calendar:
            calendar = Path(manifest.roll_calendar)
            calendar = calendar if calendar.is_absolute() else self.project_root / calendar
            if not calendar.is_file() or _file_sha256(calendar) != manifest.roll_calendar_sha256:
                raise ValueError("governed dataset roll calendar is missing or hash-drifted")
        if manifest.event_source is not None:
            event = manifest.event_source.model_dump(mode="json", exclude_none=True)
            for field, hash_field in (
                ("archive", "archive_sha256"),
                ("raw_manifest", "raw_manifest_sha256"),
                ("session_levels", "session_levels_sha256"),
                ("quality_manifest", "quality_manifest_sha256"),
                ("concordance_report", "concordance_report_sha256"),
            ):
                value = event.get(field)
                if not value:
                    continue
                artifact = _resolve_project_owned_path(value, self.project_root)
                if not artifact.is_file() or _file_sha256(artifact) != event.get(hash_field):
                    raise ValueError(f"governed event-source artifact is missing or hash-drifted: {field}")
            raw_dir = event.get("raw_dir")
            if raw_dir:
                directory = _resolve_project_owned_path(raw_dir, self.project_root)
                if not directory.is_dir():
                    raise ValueError("governed Sierra raw_dir is missing")
        return manifest

    def fixed_mechanics_validation_window(
        self,
        cfg: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Materialize the repository-wide mechanics sample for one config.

        The dates are a consequence of the governed dataset and central policy;
        they are not a per-campaign methodology choice.
        """

        dataset_id = str(
            cfg.get("dataset_id")
            or (cfg.get("data") or {}).get("dataset_id")
            or ""
        )
        if not dataset_id:
            raise ValueError("campaign config does not declare a governed dataset")
        manifest = self._load_dataset(dataset_id)
        subset = mechanics_validation_subset(
            manifest.coverage_start,
            manifest.coverage_end,
            data_path=manifest.path,
            data_source=manifest.source,
            exchange_timezone=manifest.exchange_timezone,
            project_root=self.project_root,
        )
        policy = load_research_policy().mechanics_validation
        return {
            **subset,
            "selection_mode": str(policy["selection_mode"]),
            "session_count": int(policy["session_count"]),
        }

    def _datasets_for_configs(
        self,
        configs: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, DatasetManifestV1]:
        manifests: dict[str, DatasetManifestV1] = {}
        for variant, cfg in configs.items():
            dataset_id = str(
                cfg.get("dataset_id")
                or (cfg.get("data") or {}).get("dataset_id")
                or ""
            )
            if not dataset_id:
                raise ValueError(f"parent config {variant} does not declare a governed dataset")
            manifests[variant] = self._load_dataset(dataset_id)
        return manifests

    def _validate_certified_mechanics(
        self,
        cfg: dict[str, Any],
        dataset: DatasetManifestV1,
    ) -> None:
        if cfg.get("symbol") != dataset.symbol:
            raise ValueError("follow-up dataset symbol must match the frozen campaign")
        strategy = cfg.get("strategy") if isinstance(cfg.get("strategy"), dict) else {}
        event_lane = str(cfg.get("engine_lane") or "") == "canonical_event_replay"
        if not event_lane and cfg.get("timeframe") != dataset.timeframe:
            raise ValueError(
                "bar-lane follow-up dataset timeframe must match the frozen campaign"
            )
        if event_lane:
            event = strategy.get("event") if isinstance(strategy.get("event"), dict) else {}
            try:
                certification = strategy_identity_for_config(
                    cfg, self.project_root, require_declared_match=True
                )
                if certification is None:
                    raise StrategyCertificationError("event strategy certification is missing")
                event_params = normalize_certified_event_params(
                    certification,
                    event.get("params") if isinstance(event.get("params"), dict) else {},
                )
                if event_params != event.get("params"):
                    raise StrategyCertificationError(
                        "strategy.event.params must explicitly contain every certified default"
                    )
                entry = strategy.get("entry") if isinstance(strategy.get("entry"), dict) else {}
                authored = (entry.get("params") or {}).get("mechanics")
                if authored != event_params:
                    raise StrategyCertificationError(
                        "authored event mechanics and canonical strategy.event.params have diverged"
                    )
                declared_timeframe = str(cfg.get("timeframe") or "")
                match = re.fullmatch(r"([1-9][0-9]*)m", declared_timeframe)
                bar_seconds = event_params.get("bar_seconds")
                if (
                    match is not None
                    and bar_seconds is not None
                    and int(match.group(1)) * 60 != int(bar_seconds)
                ):
                    raise StrategyCertificationError(
                        "event strategy timeframe must match its certified bar_seconds"
                    )
                core_grid = (cfg.get("core_grid") or {}).get("parameters", {})
                wfa_grid = (cfg.get("wfa") or {}).get("parameters", {})
                if core_grid != wfa_grid:
                    raise StrategyCertificationError(
                        "core and walk-forward event parameter grids must be identical"
                    )
                validate_certified_event_parameter_grid(
                    certification,
                    event_params,
                    core_grid,
                    qualified_keys=True,
                )
            except StrategyCertificationError as exc:
                raise ValueError(f"certified event parameter contract failed: {exc}") from exc
            _validate_context_bound_module_values(cfg)
            return
        grid = (cfg.get("core_grid") or {}).get("parameters")
        grid = grid if isinstance(grid, dict) else {}
        prefixes = {"entry": "entry", "sl": "sl", "tp": "tp"}
        tunable_counts: dict[str, int] = {}
        combination_count = 1
        for component, module_type in prefixes.items():
            binding = strategy.get(component)
            if not isinstance(binding, dict):
                raise ValueError(f"strategy.{component} is missing")
            component_grid = {
                key[len(f"{component}.params.") :]: values
                for key, values in grid.items()
                if key.startswith(f"{component}.params.")
            }
            validated = CERTIFIED_MODULE_CATALOG.validate_binding(
                module_type,  # type: ignore[arg-type]
                ModuleBindingV1(
                    module=str(binding.get("module") or ""),
                    params=deepcopy(binding.get("params") or {}),
                    parameter_grid=deepcopy(component_grid),
                ),
                dataset=dataset,
            )
            if validated.module != binding.get("module") or validated.params != binding.get("params"):
                raise ValueError(
                    f"strategy.{component} is not the canonical certified binding; "
                    "follow-up creation will not silently add or rewrite module parameters"
                )
            tunable_counts[component] = len(component_grid)
            for values in component_grid.values():
                if not isinstance(values, list) or not values:
                    raise ValueError("every declared parameter-grid dimension must contain values")
                combination_count *= len(values)
        if tunable_counts["entry"] > 2 or tunable_counts["sl"] > 1 or tunable_counts["tp"] > 1:
            raise ValueError("follow-up mechanics exceed the two-entry, one-stop, one-target tunable caps")
        if combination_count != 1 and not 8 <= combination_count <= 120:
            raise ValueError("follow-up parameter space must contain exactly one or between 8 and 120 combinations")
        _validate_context_bound_module_values(cfg)


def _apply_attempt_identity(
    cfg: dict[str, Any],
    *,
    evidence_root: Path,
    approval_root: Path,
    campaign_id: str,
    variant_id: str,
    attempt_id: str,
    attempt_kind: str,
    parent_attempt_id: str,
    reason: str,
    created_by: str,
    parent_variant_id: str,
    rescue_target_variant_id: str | None,
) -> None:
    cfg["attempt_id"] = attempt_id
    cfg["attempt_kind"] = attempt_kind
    cfg["attempt_provenance"] = "authored"
    cfg["parent_attempt_id"] = parent_attempt_id
    cfg["test_run_id"] = f"attempt_{attempt_id}"
    research = cfg.setdefault("research_metadata", {})
    research["parent_variant_id"] = parent_variant_id
    if rescue_target_variant_id is not None:
        research["rescue_target_variant_id"] = rescue_target_variant_id
    else:
        research.pop("rescue_target_variant_id", None)
    research["follow_up"] = {
        "schema": FOLLOW_UP_SCHEMA,
        "attempt_id": attempt_id,
        "attempt_kind": attempt_kind,
        "parent_attempt_id": parent_attempt_id,
        "reason": reason,
        "created_by": created_by,
    }
    gate = research.get("validation_gate")
    if not isinstance(gate, dict) or gate.get("required") is not True:
        raise ValueError(f"{variant_id} does not declare mandatory mechanics validation")
    symbol = str(cfg.get("symbol") or (cfg.get("data") or {}).get("symbol") or "")
    gate["evidence_dir"] = str(
        evidence_root
        / campaign_id
        / variant_id
        / symbol
        / f"mechanics_validation_{attempt_id}"
        / "validation_runs/core"
    )
    gate["approval_path"] = str(approval_root / campaign_id / attempt_id / variant_id / "approval.json")
    for field in ("evidence_dir", "approval_path"):
        if Path(gate[field]).exists():
            raise FileExistsError(f"fresh follow-up {field} already exists: {gate[field]}")
    run_path = evidence_root / campaign_id / variant_id / symbol / str(cfg["test_run_id"])
    if run_path.exists():
        raise FileExistsError(f"fresh follow-up staged-run path already exists: {run_path}")


def _resolve_project_owned_path(value: str | Path, project_root: Path) -> Path:
    """Resolve a governed path after the repository itself has moved."""

    path = Path(value)
    if not path.is_absolute():
        return project_root / path
    if path.exists():
        return path
    parts = path.parts
    for anchor in ("data", "research", "research_artifacts", "run-store"):
        if anchor not in parts:
            continue
        candidate = project_root.joinpath(*parts[parts.index(anchor) :])
        if candidate.exists():
            return candidate
    return path


def _rebase_relocated_project_paths(
    cfg: dict[str, Any],
    *,
    variant_id: str,
    project_root: Path,
) -> list[dict[str, Any]]:
    """Make project-owned operational paths portable in a fresh child."""

    data = cfg.get("data") if isinstance(cfg.get("data"), dict) else {}
    execution = (
        data.get("execution_data")
        if isinstance(data.get("execution_data"), dict)
        else {}
    )
    raw_dir = execution.get("raw_dir")
    if not raw_dir:
        return []
    original = Path(str(raw_dir))
    resolved = _resolve_project_owned_path(original, project_root)
    if not original.is_absolute() or resolved == original or not resolved.is_dir():
        return []
    try:
        portable = resolved.relative_to(project_root).as_posix()
    except ValueError:
        return []
    execution["raw_dir"] = portable
    changes = [
        {
            "variant_id": variant_id,
            "scope": "operational_storage",
            "field": "data.execution_data.raw_dir",
            "old": str(original),
            "new": portable,
            "reviewed": True,
        }
    ]
    factory = cfg.get("research_factory")
    objectives = cfg.get("research_objectives")
    if (
        isinstance(factory, dict)
        and factory.get("schema") == "alphaquest.research-factory-binding/v2"
        and isinstance(objectives, dict)
    ):
        old_factory = deepcopy(factory)
        policy = load_research_policy()
        cfg["research_factory"] = research_factory_binding(
            objectives,
            dataset={
                "dataset_id": cfg.get("dataset_id") or data.get("dataset_id"),
                "canonical_sha256": data.get("canonical_sha256"),
                "source_sha256": data.get("source_sha256"),
                "coverage_start": data.get("coverage_start"),
                "coverage_end": data.get("coverage_end"),
                "roll_calendar_sha256": data.get("roll_calendar_sha256"),
                "execution_data": execution,
            },
            acceptance_train_months=int(policy.acceptance_oos["train_months"]),
            acceptance_test_months=int(policy.acceptance_oos["test_months"]),
        )
        changes.append(
            {
                "variant_id": variant_id,
                "scope": "research_factory",
                "field": "dataset.event_execution_contract_sha256",
                "old": old_factory["dataset"].get(
                    "event_execution_contract_sha256"
                ),
                "new": cfg["research_factory"]["dataset"].get(
                    "event_execution_contract_sha256"
                ),
                "reviewed": True,
                "change_kind": "operational_path_rebind",
            }
        )
    return changes


def _validate_context_bound_module_values(cfg: Mapping[str, Any]) -> None:
    strategy = cfg.get("strategy") or {}
    entry = strategy.get("entry") or {}
    entry_params = entry.get("params") or {}
    timeframe = str(cfg.get("timeframe") or "")
    if not timeframe.endswith("m"):
        raise ValueError("Studio follow-ups support only frozen intraday minute-bar campaigns")
    interval = float(timeframe[:-1])
    declared_interval = (
        (entry_params.get("rule") or {}).get("bar_interval_minutes")
        if entry.get("module") == "safe_bar_rule"
        else entry_params.get("bar_interval_minutes")
    )
    if declared_interval is not None and float(declared_interval) != interval:
        raise ValueError("entry bar interval cannot diverge from the frozen campaign timeframe")
    data = cfg.get("data") or {}
    apex = cfg.get("apex_rules") or {}
    session_start = _clock(data.get("rth_start"))
    session_end = _clock(data.get("rth_end"))
    latest_entry = _clock(apex.get("latest_entry_time"))
    module = str(entry.get("module") or "")
    if module == "safe_bar_rule":
        rule = entry_params.get("rule") or {}
        signal_start = _clock(rule.get("signal_start_time"))
        signal_end = _clock(rule.get("signal_end_time"))
        if session_start and signal_start and signal_start < session_start:
            raise ValueError("safe-rule signal_start_time cannot precede the reviewed session")
        if latest_entry and signal_end and signal_end > latest_entry:
            raise ValueError("safe-rule signal_end_time cannot exceed the reviewed entry cutoff")
    elif module == "calendar_session_bias":
        signal_time = _clock(entry_params.get("signal_time"))
        if session_start and signal_time and signal_time < session_start:
            raise ValueError("calendar signal_time cannot precede the reviewed session")
        if latest_entry and signal_time and signal_time > latest_entry:
            raise ValueError("calendar signal_time cannot exceed the reviewed entry cutoff")
    elif module == "opening_range_breakout":
        if session_start and _clock(entry_params.get("rth_start")) != session_start:
            raise ValueError("opening-range rth_start must match the reviewed session")
        configured_last = _clock(entry_params.get("last_entry_time"))
        if latest_entry and configured_last and configured_last > latest_entry:
            raise ValueError("opening-range last_entry_time cannot exceed the reviewed entry cutoff")
    elif module == "daily_time_series_momentum" and session_end:
        if _clock(entry_params.get("rth_end")) != session_end:
            raise ValueError("time-series-momentum rth_end must match the reviewed session")

    core = cfg.get("core") or {}
    stop = strategy.get("sl") or {}
    stop_params = stop.get("params") or {}
    if stop.get("module") == "fixed_dollar_per_contract" and float(stop_params.get("tick_value") or 0) != float(
        core.get("tick_value") or 0
    ):
        raise ValueError("fixed-dollar stop tick_value must match the reviewed execution contract")
    target = strategy.get("tp") or {}
    target_params = target.get("params") or {}
    if target.get("module") == "cost_adjusted_fixed_r":
        expected = {
            "tick_size": core.get("tick_size"),
            "tick_value": core.get("tick_value"),
            "commission_per_contract": core.get("commission_per_contract"),
            "slippage_ticks": core.get("slippage_ticks"),
        }
        mismatches = [
            name for name, value in expected.items() if float(target_params.get(name) or 0) != float(value or 0)
        ]
        if mismatches:
            raise ValueError(
                "cost-adjusted target parameters must match the reviewed execution contract: " + ", ".join(mismatches)
            )


def _clock(value: Any) -> time | None:
    if value in {None, ""}:
        return None
    try:
        return time.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"invalid reviewed session time: {value!r}") from exc


def _apply_dataset_refresh(
    cfg: dict[str, Any],
    manifest: DatasetManifestV1,
    *,
    variant_id: str,
    project_root: Path,
) -> list[dict[str, Any]]:
    if cfg.get("symbol") != manifest.symbol or cfg.get("timeframe") != manifest.timeframe:
        raise ValueError("data refresh cannot change the frozen campaign symbol or timeframe")
    old_dataset = str(cfg.get("dataset_id") or (cfg.get("data") or {}).get("dataset_id") or "")
    cfg["dataset_id"] = manifest.dataset_id
    data = cfg.setdefault("data", {})
    for key in ("raw_csv", "raw_parquet", "roll_calendar", "roll_calendar_sha256"):
        data.pop(key, None)
    source_key = "raw_parquet" if manifest.source == "parquet" else "raw_csv"
    data.update(
        {
            "dataset_id": manifest.dataset_id,
            "source_timeframe": manifest.timeframe,
            "source": manifest.source,
            source_key: manifest.path,
            "symbol": manifest.symbol,
            "timezone": manifest.exchange_timezone,
            "source_timezone": manifest.timezone,
            "exchange_timezone": manifest.exchange_timezone,
            "timestamp_semantics": manifest.timestamp_semantics,
            "source_timestamp_semantics": manifest.source_timestamp_semantics or manifest.timestamp_semantics,
            "source_sha256": manifest.source_sha256,
            "canonical_sha256": manifest.canonical_sha256,
            "coverage_start": manifest.coverage_start,
            "coverage_end": manifest.coverage_end,
            "roll_policy": manifest.roll_policy,
            "continuous_contract": manifest.continuous_contract,
            "contract_column": manifest.contract_column,
            "contract_count": manifest.contract_count,
            "certified_features": list(manifest.certified_features),
        }
    )
    if manifest.roll_calendar:
        data["roll_calendar"] = manifest.roll_calendar
        data["roll_calendar_sha256"] = manifest.roll_calendar_sha256
    old_execution = deepcopy(data.get("execution_data"))
    if str(cfg.get("engine_lane") or "") == "canonical_event_replay":
        if manifest.event_source is None:
            raise ValueError("canonical event data refresh requires a governed event_source")
        data["execution_data"] = manifest.event_source.model_dump(mode="json", exclude_none=True)
        strategy = cfg.get("strategy") if isinstance(cfg.get("strategy"), dict) else {}
        event = strategy.get("event") if isinstance(strategy.get("event"), dict) else {}
        certification = get_strategy_certification(
            str(event.get("module") or ""), project_root, require_current=True
        )
        cfg["strategy_certification"] = {
            "strategy_id": certification.strategy_id,
            "implementation_version": certification.implementation_version,
            "implementation_sha256": certification.implementation_sha256,
            "manifest_sha256": certification.manifest_sha256,
        }
    factory_binding = cfg.get("research_factory")
    if (
        isinstance(factory_binding, Mapping)
        and factory_binding.get("schema") == "alphaquest.research-factory-binding/v2"
    ):
        objectives = cfg.get("research_objectives")
        if not isinstance(objectives, Mapping):
            raise ValueError("v2 research_factory data refresh requires frozen research objectives")
        policy = load_research_policy()
        old_factory_binding = deepcopy(factory_binding)
        factory_dataset = manifest.model_dump(mode="json", by_alias=True)
        if str(cfg.get("engine_lane") or "") != "canonical_event_replay":
            factory_dataset.pop("event_source", None)
        cfg["research_factory"] = research_factory_binding(
            objectives,
            dataset=factory_dataset,
            acceptance_train_months=int(policy.acceptance_oos["train_months"]),
            acceptance_test_months=int(policy.acceptance_oos["test_months"]),
        )
    else:
        old_factory_binding = None
    full = {
        "start_date": manifest.coverage_start[:10],
        "end_date": manifest.coverage_end[:10],
        "session_labels": ["RTH"],
    }
    for key in ("core", "core_grid", "monkey", "wfa"):
        section = cfg.get(key)
        if isinstance(section, dict):
            section["data_subset"] = deepcopy(full)
    gate = (cfg.get("research_metadata") or {}).get("validation_gate") or {}
    strategy = cfg.get("strategy") if isinstance(cfg.get("strategy"), Mapping) else {}
    entry = strategy.get("entry") if isinstance(strategy.get("entry"), Mapping) else {}
    entry_binding = ModuleBindingV1.model_validate(
        {
            "module": entry.get("module"),
            "params": deepcopy(entry.get("params") or {}),
            "parameter_grid": {},
        }
    )
    gate["data_subset"] = mechanics_validation_subset(
        manifest.coverage_start,
        manifest.coverage_end,
        entry=entry_binding,
        data_path=manifest.path,
        data_source=manifest.source,
        exchange_timezone=manifest.exchange_timezone,
        project_root=project_root,
    )
    gate.update(deepcopy(load_research_policy().mechanics_validation))
    changes = [
        {
            "variant_id": variant_id,
            "scope": "dataset",
            "field": "dataset_id",
            "old": old_dataset,
            "new": manifest.dataset_id,
            "reviewed": True,
        }
    ]
    if old_factory_binding is not None:
        changes.append(
            {
                "variant_id": variant_id,
                "scope": "research_factory",
                "field": "locked_acceptance_dataset_and_calendar",
                "old": old_factory_binding,
                "new": deepcopy(cfg["research_factory"]),
                "reviewed": True,
            }
        )
    if old_execution != data.get("execution_data"):
        changes.append(
            {
                "variant_id": variant_id,
                "scope": "data.execution_data",
                "field": "source",
                "old": (old_execution or {}).get("source") if isinstance(old_execution, dict) else None,
                "new": (data.get("execution_data") or {}).get("source"),
                "reviewed": True,
            }
        )
    return changes


def _apply_execution_timeline(
    cfg: dict[str, Any],
    timeline: ExecutionTimelinePatchV1,
    *,
    variant_id: str,
) -> list[dict[str, Any]]:
    if str(cfg.get("engine_lane") or "") != "canonical_event_replay":
        raise ValueError(
            "execution timeline correction requires canonical event replay"
        )
    execution = ((cfg.get("data") or {}).get("execution_data") or {})
    source_end = str(execution.get("rth_end") or "")
    if source_end and timeline.flatten_time > source_end:
        raise ValueError(
            "flatten_time cannot exceed the governed event-source RTH boundary"
        )
    event_params = (
        (((cfg.get("strategy") or {}).get("event") or {}).get("params") or {})
    )
    certified_limit = int(event_params.get("max_trades_per_day", -1))
    if certified_limit != timeline.max_trades_per_day:
        raise ValueError(
            "execution timeline daily limit must match certified "
            "strategy.event.params.max_trades_per_day"
        )

    changes: list[dict[str, Any]] = []
    paths = (
        ("core", "latest_entry_time", timeline.latest_entry_time),
        ("core", "flatten_time", timeline.flatten_time),
        ("core", "max_trades_per_day", timeline.max_trades_per_day),
        ("strategy", "flatten_time", timeline.flatten_time),
        ("apex_rules", "latest_entry_time", timeline.latest_entry_time),
        ("apex_rules", "force_flatten_time", timeline.flatten_time),
        ("apex_rules", "latest_flat_time", timeline.flatten_time),
    )
    for section_name, field_name, new_value in paths:
        section = cfg.setdefault(section_name, {})
        old_value = section.get(field_name)
        section[field_name] = new_value
        changes.append(
            {
                "variant_id": variant_id,
                "scope": section_name,
                "field": field_name,
                "old": old_value,
                "new": new_value,
                "reviewed": True,
            }
        )
    research = cfg.setdefault("research_metadata", {})
    mechanics_review = research.get("mechanics_review")
    if isinstance(mechanics_review, dict):
        field_name = "target_exit_rationale"
        old_rationale = str(mechanics_review.get(field_name) or "").strip()
        flatten_label = timeline.flatten_time[:5]
        if re.search(
            r"\b\d{1,2}:\d{2}(?::\d{2})?\s+forced flatten\b",
            old_rationale,
        ):
            new_rationale = re.sub(
                r"\b\d{1,2}:\d{2}(?::\d{2})?\s+forced flatten\b",
                f"{flatten_label} forced flatten",
                old_rationale,
            )
        else:
            new_rationale = (
                f"{old_rationale.rstrip('.')}."
                if old_rationale
                else ""
            )
            new_rationale += (
                f" Positions and pending orders are forced flat at {flatten_label} ET."
            )
            new_rationale = new_rationale.strip()
        mechanics_review[field_name] = new_rationale
        changes.append(
            {
                "variant_id": variant_id,
                "scope": "research_metadata.mechanics_review",
                "field": field_name,
                "old": old_rationale,
                "new": new_rationale,
                "reviewed": True,
            }
        )
    daily_limit = (
        "no daily trade-count cap"
        if timeline.max_trades_per_day == 0
        else f"a maximum of {timeline.max_trades_per_day} entries per session"
    )
    research["timeframe_rationale"] = (
        "Trade events are replayed throughout RTH from 09:30 to 16:00 New York. "
        f"New entries are accepted through {timeline.latest_entry_time}, all "
        f"positions and pending orders flatten at {timeline.flatten_time}, and "
        f"{daily_limit} is applied."
    )
    return changes


def _apply_certification_refresh(
    cfg: dict[str, Any],
    *,
    variant_id: str,
    project_root: Path,
    replacement_strategy_id: str | None = None,
) -> list[dict[str, Any]]:
    """Bind a pre-PnL attempt to a newly certified implementation.

    This is deliberately separate from scalar mechanics edits.  It is the
    governed publication path when reviewed source logic changes while the
    strategy remains the same campaign variant.
    """

    if str(cfg.get("engine_lane") or "") != "canonical_event_replay":
        raise ValueError("certification refresh requires the canonical event-replay lane")
    strategy = cfg.get("strategy") if isinstance(cfg.get("strategy"), dict) else {}
    event = strategy.get("event") if isinstance(strategy.get("event"), dict) else {}
    old_module = str(event.get("module") or "")
    module = str(replacement_strategy_id or old_module)
    certification = get_strategy_certification(module, project_root, require_current=True)
    old_identity = deepcopy(cfg.get("strategy_certification") or {})
    new_identity = {
        "strategy_id": certification.strategy_id,
        "implementation_version": certification.implementation_version,
        "implementation_sha256": certification.implementation_sha256,
        "manifest_sha256": certification.manifest_sha256,
    }

    old_event_params = deepcopy(event.get("params") or {})
    if not isinstance(old_event_params, dict):
        raise ValueError("strategy.event.params must be a mapping")
    entry = strategy.get("entry") if isinstance(strategy.get("entry"), dict) else {}
    entry_params = entry.get("params") if isinstance(entry.get("params"), dict) else {}
    old_authored = deepcopy(entry_params.get("mechanics") or {})
    if old_authored != old_event_params:
        raise ValueError("authored event mechanics and canonical strategy.event.params have diverged")

    retired_parameters = sorted(set(old_event_params) - set(certification.parameters))
    strategy_replaced = module != old_module
    retained_event_params = (
        {}
        if strategy_replaced
        else {
            name: value
            for name, value in old_event_params.items()
            if name in certification.parameters
        }
    )
    migrated_fixed_defaults: list[str] = []
    for name, value in list(retained_event_params.items()):
        parameter = certification.parameters[name]
        try:
            validate_certified_parameter_value(
                parameter,
                value,
                context=certification.strategy_id,
            )
        except StrategyCertificationError:
            if parameter.studio_editable or parameter.tunable:
                raise
            retained_event_params[name] = parameter.default
            migrated_fixed_defaults.append(name)
    normalized = normalize_certified_event_params(certification, retained_event_params)
    context_coverage_changes = _apply_certified_context_coverage_start(
        cfg,
        normalized,
        variant_id=variant_id,
        project_root=project_root,
    )
    core_grid = (cfg.get("core_grid") or {}).get("parameters", {})
    wfa_grid = (cfg.get("wfa") or {}).get("parameters", {})
    if core_grid != wfa_grid:
        raise ValueError("core and walk-forward event parameter grids must be identical")
    retired_grid_dimensions: dict[str, list[Any]] = {}
    reset_grid_dimensions: dict[str, list[Any]] = {}
    retained_grid: dict[str, list[Any]] = {}
    for qualified_name, values in core_grid.items():
        parameter_name = str(qualified_name).removeprefix("event.params.")
        parameter = certification.parameters.get(parameter_name)
        if parameter is None or not parameter.tunable:
            retired_grid_dimensions[str(qualified_name)] = deepcopy(values)
        else:
            retained_grid[str(qualified_name)] = deepcopy(values)
    retained_combination_count = math.prod(
        len(values) for values in retained_grid.values()
    )
    if retained_grid and not 8 <= retained_combination_count <= 120:
        # A source-level mechanics correction can retire only part of an old
        # grid, leaving a residual parameter space that is too small to be a
        # governed optimization declaration.  Freeze the correction at the
        # reviewed defaults; a separate immutable parameter-declaration child
        # must install the replacement grid before any performance stage.
        reset_grid_dimensions = deepcopy(retained_grid)
        retained_grid = {}
    canonical_grid = (
        {}
        if strategy_replaced
        else validate_certified_event_parameter_grid(
            certification,
            normalized,
            retained_grid,
            qualified_keys=True,
        )
    )

    changed_defaults = [
        name for name in normalized if name not in old_event_params or old_event_params[name] != normalized[name]
    ]
    if old_identity == new_identity and not changed_defaults and not strategy_replaced:
        raise ValueError("certification refresh must bind a materially new certified implementation")

    # A new implementation version may retain the stable strategy ID while
    # changing one of its certified module bindings. Always synchronize the
    # bindings; limiting this to an ID replacement leaves same-package
    # upgrades with stale entry/stop/target identities.
    event["module"] = certification.strategy_id
    entry["module"] = certification.entry_module
    stop = strategy.setdefault("sl", {})
    stop["module"] = certification.stop_module
    stop["params"] = {}
    target = strategy.setdefault("tp", {})
    target["module"] = certification.target_module
    target["params"] = {}
    cfg["strategy_name"] = certification.strategy_id

    if strategy_replaced:
        core = cfg.setdefault("core", {})
        execution_values = {
            "tick_size": normalized.get("tick_size"),
            "point_value": normalized.get("point_value"),
            "commission_per_contract": normalized.get("commission_per_contract"),
            "slippage_ticks": normalized.get("slippage_ticks"),
            "max_trades_per_day": normalized.get("max_trades_per_day"),
            "contracts": normalized.get("contracts"),
            "initial_balance": normalized.get("initial_balance"),
        }
        for name, value in execution_values.items():
            if value is not None:
                core[name] = value
        if (
            execution_values["tick_size"] is not None
            and execution_values["point_value"] is not None
        ):
            core["tick_value"] = (
                float(execution_values["tick_size"])
                * float(execution_values["point_value"])
            )
        sizing = core.setdefault("position_sizing", {})
        if execution_values["contracts"] is not None:
            sizing["mode"] = "fixed_contracts"
            sizing["contracts"] = execution_values["contracts"]
    event["params"] = deepcopy(normalized)
    entry_params["mechanics"] = deepcopy(normalized)
    cfg.setdefault("core_grid", {})["parameters"] = deepcopy(canonical_grid)
    cfg.setdefault("wfa", {})["parameters"] = deepcopy(canonical_grid)
    cfg["strategy_certification"] = deepcopy(new_identity)
    research = cfg.setdefault("research_metadata", {})
    reviewed_mechanics = certification.studio.get("mechanics_review")
    if isinstance(reviewed_mechanics, dict):
        research["mechanics_review"] = deepcopy(reviewed_mechanics)
        timeframe_rationale = certification.studio.get("timeframe_rationale")
        if timeframe_rationale:
            research["timeframe_rationale"] = str(timeframe_rationale)
    validation_gate = research.setdefault("validation_gate", {})
    old_minimum_trade_samples = validation_gate.get(
        "minimum_trade_samples"
    )
    mechanics_validation = certification.studio.get(
        "mechanics_validation"
    )
    if isinstance(mechanics_validation, dict):
        required_samples = int(
            mechanics_validation.get("minimum_trade_samples") or 1
        )
        if required_samples < 1:
            raise ValueError(
                "certified minimum_trade_samples must be positive"
            )
        validation_gate["minimum_trade_samples"] = required_samples

    execution_changes = apply_certified_execution_contract(
        cfg,
        certification,
        variant_id=variant_id,
    )
    changes = [
        {
            "variant_id": variant_id,
            "scope": "strategy_certification",
            "field": "certified_implementation_identity",
            "old": old_identity,
            "new": new_identity,
            "reviewed": True,
        }
    ]
    changes.extend(execution_changes)
    changes.extend(context_coverage_changes)
    if (
        validation_gate.get("minimum_trade_samples")
        != old_minimum_trade_samples
    ):
        changes.append(
            {
                "variant_id": variant_id,
                "scope": "research_metadata.validation_gate",
                "field": "minimum_trade_samples",
                "old": old_minimum_trade_samples,
                "new": validation_gate["minimum_trade_samples"],
                "reviewed": True,
            }
        )
    if migrated_fixed_defaults:
        changes.append(
            {
                "variant_id": variant_id,
                "scope": "strategy.event.params",
                "field": "migrated_fixed_certified_defaults",
                "old": {
                    name: old_event_params[name]
                    for name in migrated_fixed_defaults
                },
                "new": {
                    name: normalized[name]
                    for name in migrated_fixed_defaults
                },
                "reviewed": True,
            }
        )
    if strategy_replaced:
        changes.append(
            {
                "variant_id": variant_id,
                "scope": "strategy",
                "field": "certified_strategy_package",
                "old": old_module,
                "new": certification.strategy_id,
                "reviewed": True,
            }
        )
    changes.extend(
        {
            "variant_id": variant_id,
            "scope": "strategy.event.params,strategy.entry.params.mechanics",
            "field": name,
            "old": old_event_params[name],
            "new": None,
            "reviewed": True,
            "change_kind": "retired_certified_parameter",
        }
        for name in retired_parameters
    )
    changes.extend(
        {
            "variant_id": variant_id,
            "scope": "core_grid.parameters,wfa.parameters",
            "field": name,
            "old": values,
            "new": None,
            "reviewed": True,
            "change_kind": "retired_certified_grid_dimension",
        }
        for name, values in retired_grid_dimensions.items()
    )
    changes.extend(
        {
            "variant_id": variant_id,
            "scope": "core_grid.parameters,wfa.parameters",
            "field": name,
            "old": values,
            "new": None,
            "reviewed": True,
            "change_kind": "incomplete_inherited_grid_reset_to_defaults",
        }
        for name, values in reset_grid_dimensions.items()
    )
    changes.extend(
        {
            "variant_id": variant_id,
            "scope": "strategy.event.params,strategy.entry.params.mechanics",
            "field": name,
            "old": old_event_params.get(name),
            "new": normalized[name],
            "reviewed": True,
        }
        for name in changed_defaults
    )
    return changes


def _apply_certified_context_coverage_start(
    cfg: dict[str, Any],
    normalized_event_params: Mapping[str, Any],
    *,
    variant_id: str,
    project_root: Path,
) -> list[dict[str, Any]]:
    """Exclude only the causal warm-up prefix missing a certified context seed."""

    path_text = normalized_event_params.get("big_trade_context_path")
    expected_sha256 = normalized_event_params.get("big_trade_context_sha256")
    if not path_text or not expected_sha256:
        return []
    path = Path(str(path_text)).expanduser()
    if not path.is_absolute():
        path = project_root / path
    if not path.is_file():
        raise ValueError(f"certified big-trade context is missing: {path}")
    actual_sha256 = _file_sha256(path)
    if actual_sha256 != str(expected_sha256):
        raise ValueError(
            "certified big-trade context hash drift: "
            f"expected {expected_sha256}, got {actual_sha256}"
        )
    frame = pd.read_parquet(path, columns=["session_date"])
    if frame.empty:
        raise ValueError("certified big-trade context contains no session rows")
    coverage_start = str(frame["session_date"].astype(str).min())
    changes: list[dict[str, Any]] = []
    for section_name in ("core", "core_grid", "monkey", "wfa"):
        section = cfg.get(section_name)
        subset = (
            section.get("data_subset")
            if isinstance(section, dict)
            else None
        )
        if not isinstance(subset, dict):
            continue
        old_start = str(subset.get("start_date") or "")
        if not old_start or old_start >= coverage_start:
            continue
        subset["start_date"] = coverage_start
        changes.append(
            {
                "variant_id": variant_id,
                "scope": f"{section_name}.data_subset",
                "field": "start_date",
                "old": old_start,
                "new": coverage_start,
                "reviewed": True,
                "change_kind": "causal_context_warmup",
            }
        )
    return changes


def _apply_mechanic_patch(
    cfg: dict[str, Any],
    patch: MechanicParameterPatchV1,
) -> dict[str, Any]:
    strategy = cfg.get("strategy")
    component = strategy.get(patch.component) if isinstance(strategy, dict) else None
    params = component.get("params") if isinstance(component, dict) else None
    if not isinstance(params, dict):
        raise ValueError(f"{patch.variant_id} strategy.{patch.component}.params is not editable")
    parts = patch.parameter_path.split(".")
    parent = params
    for part in parts[:-1]:
        value = parent.get(part)
        if not isinstance(value, dict):
            raise ValueError(
                f"mechanics patch path does not identify an existing nested parameter: {patch.parameter_path}"
            )
        parent = value
    leaf = parts[-1]
    if leaf not in parent:
        raise ValueError(f"mechanics patch parameter does not exist: {patch.parameter_path}")
    old = parent[leaf]
    if isinstance(old, (dict, list)) or not isinstance(old, (str, int, float, bool, type(None))):
        raise ValueError("Studio follow-up UI may patch only an existing scalar module parameter")
    if type(old) is not type(patch.value) and not (
        isinstance(old, (int, float))
        and not isinstance(old, bool)
        and isinstance(patch.value, (int, float))
        and not isinstance(patch.value, bool)
    ):
        raise ValueError("mechanics patch value must preserve the existing parameter type")
    if old == patch.value:
        raise ValueError("mechanics patch must materially change the selected parameter")
    parent[leaf] = patch.value
    strategy = cfg.get("strategy") if isinstance(cfg.get("strategy"), dict) else {}
    event = strategy.get("event") if isinstance(strategy.get("event"), dict) else None
    if event is not None and patch.component == "entry" and parts[0] == "mechanics" and len(parts) == 2:
        event_params = event.get("params") if isinstance(event.get("params"), dict) else None
        if event_params is None or leaf not in event_params or event_params[leaf] != old:
            raise ValueError("canonical event parameter is missing or has diverged from authored mechanics")
        event_params[leaf] = patch.value
    return {
        "variant_id": patch.variant_id,
        "scope": f"strategy.{patch.component}.params",
        "field": patch.parameter_path,
        "old": old,
        "new": patch.value,
        "reviewed": True,
    }


def _apply_parameter_declaration(
    cfg: dict[str, Any],
    parameter_grid: Mapping[str, list[JsonScalar]],
    *,
    project_root: Path,
) -> list[dict[str, Any]]:
    if str(cfg.get("engine_lane") or "") != "canonical_event_replay":
        raise ValueError("pre-PnL parameter declaration currently supports certified event strategies only")
    strategy = cfg.get("strategy") if isinstance(cfg.get("strategy"), dict) else {}
    event = strategy.get("event") if isinstance(strategy.get("event"), dict) else {}
    certification = get_strategy_certification(
        str(event.get("module") or ""), project_root, require_current=True
    )
    params = normalize_certified_event_params(
        certification,
        event.get("params") if isinstance(event.get("params"), dict) else {},
    )
    canonical = validate_certified_event_parameter_grid(
        certification,
        params,
        {str(name): list(values) for name, values in parameter_grid.items()},
    )
    old_core = deepcopy((cfg.get("core_grid") or {}).get("parameters") or {})
    old_wfa = deepcopy((cfg.get("wfa") or {}).get("parameters") or {})
    if old_core == canonical and old_wfa == canonical:
        raise ValueError("parameter declaration must differ from the parent attempt")
    cfg.setdefault("core_grid", {})["parameters"] = deepcopy(canonical)
    cfg.setdefault("wfa", {})["parameters"] = deepcopy(canonical)
    cfg["strategy_certification"] = {
        "strategy_id": certification.strategy_id,
        "implementation_version": certification.implementation_version,
        "implementation_sha256": certification.implementation_sha256,
        "manifest_sha256": certification.manifest_sha256,
    }
    gate = (cfg.setdefault("research_metadata", {})).setdefault("validation_gate", {})
    gate["parameter_mode"] = "declared_defaults"
    return [
        {
            "variant_id": str(cfg.get("variant_id") or ""),
            "scope": "core_grid.parameters,wfa.parameters",
            "field": name,
            "old": old_core.get(name),
            "new": values,
            "reviewed": True,
        }
        for name, values in canonical.items()
    ]


def _apply_mechanics_validation_window(
    cfg: dict[str, Any],
    window: MechanicsValidationWindowV1,
    *,
    dataset_manifest: DatasetManifestV1,
    project_root: Path,
) -> dict[str, Any] | None:
    coverage_start = date.fromisoformat(dataset_manifest.coverage_start[:10])
    coverage_end = date.fromisoformat(dataset_manifest.coverage_end[:10])
    start = date.fromisoformat(window.start_date)
    end = date.fromisoformat(window.end_date)
    if start < coverage_start or end > coverage_end:
        raise ValueError(
            "mechanics validation window must remain inside governed dataset coverage "
            f"{coverage_start.isoformat()} through {coverage_end.isoformat()}"
        )
    required_count = int(
        load_research_policy().mechanics_validation["session_count"]
    )
    if window.session_count != required_count:
        raise ValueError(
            f"mechanics validation must use the repository-wide {required_count}-session policy"
        )
    if window.session_count:
        data_path = Path(dataset_manifest.path)
        if not data_path.is_absolute():
            data_path = project_root / data_path
        if not data_path.is_file():
            raise ValueError(
                f"mechanics validation session source does not exist: {data_path}"
            )
        if dataset_manifest.source == "parquet":
            timestamps = pd.read_parquet(data_path, columns=["timestamp"])["timestamp"]
        else:
            timestamps = pd.read_csv(data_path, usecols=["timestamp"])["timestamp"]
        local_dates = pd.to_datetime(timestamps, utc=True).dt.tz_convert(
            dataset_manifest.exchange_timezone
        ).dt.date
        sessions = sorted(set(local_dates))
        selected = sessions[-required_count:]
        expected_start = selected[0]
        expected_end = selected[-1]
        actual_count = int(local_dates[(local_dates >= start) & (local_dates <= end)].nunique())
        if actual_count != window.session_count:
            raise ValueError(
                "mechanics validation window must contain exactly the declared "
                f"{window.session_count} sessions; found {actual_count}"
            )
        if (start, end) != (expected_start, expected_end):
            raise ValueError(
                "mechanics validation must use the latest eligible sessions in the governed "
                f"dataset ({expected_start.isoformat()} through {expected_end.isoformat()})"
            )
    research = cfg.setdefault("research_metadata", {})
    gate = research.get("validation_gate")
    if not isinstance(gate, dict) or gate.get("required") is not True:
        raise ValueError("methodology rerun requires mandatory mechanics validation")
    old = deepcopy(gate.get("data_subset") or {})
    new = {
        "start_date": window.start_date,
        "end_date": window.end_date,
        "session_dates": [value.isoformat() for value in selected],
    }
    gate["data_subset"] = deepcopy(new)
    gate.update(deepcopy(load_research_policy().mechanics_validation))
    if old == new:
        return None
    return {
        "variant_id": window.variant_id,
        "scope": "research_metadata.validation_gate",
        "field": "data_subset",
        "old": old,
        "new": new,
        "reviewed": True,
    }


def _attempt_strategy_spec(
    request: FollowUpAttemptRequestV1,
    attempt_id: str,
    created_at: datetime,
    configs: Mapping[str, Mapping[str, Any]],
    changes: list[dict[str, Any]],
) -> dict[str, Any]:
    target_config = (
        configs.get(str(request.target_variant_id or ""))
        if request.target_variant_id is not None
        else None
    )
    objectives = (
        deepcopy(target_config.get("research_objectives"))
        if isinstance(target_config, Mapping)
        and isinstance(target_config.get("research_objectives"), Mapping)
        else None
    )
    objectives_sha256 = (
        str(target_config.get("research_objectives_sha256") or "")
        if isinstance(target_config, Mapping)
        else ""
    )
    document = {
        "schema": "alphaquest.follow-up-strategy-spec/v1",
        "campaign_id": request.campaign_id,
        "attempt_id": attempt_id,
        "attempt_kind": request.attempt_kind,
        "parent_attempt_id": request.parent_attempt_id,
        "reason": request.reason,
        "created_by": request.created_by,
        "authorized_by": request.authorized_by,
        "created_at": created_at.isoformat(),
        "frozen": True,
        "changes": deepcopy(changes),
        "variants": [
            {
                "variant_id": variant,
                "mechanic_signature": (cfg.get("research_metadata") or {}).get("mechanic_signature"),
                "strategy": deepcopy(cfg.get("strategy")),
                "parameter_grid": deepcopy((cfg.get("core_grid") or {}).get("parameters") or {}),
                "dataset_id": cfg.get("dataset_id"),
                "validation_gate": deepcopy((cfg.get("research_metadata") or {}).get("validation_gate")),
            }
            for variant, cfg in configs.items()
        ],
    }
    if objectives is not None and objectives_sha256:
        document["research_objectives"] = objectives
        document["research_objectives_sha256"] = objectives_sha256
    if isinstance(target_config, Mapping):
        destination_contract = target_config.get("destination_benchmark_contract")
        destination_hash = str(
            target_config.get("destination_benchmark_contract_sha256") or ""
        )
        if isinstance(destination_contract, Mapping) and destination_hash:
            document["destination_benchmark_contract"] = deepcopy(
                destination_contract
            )
            document["destination_benchmark_contract_sha256"] = destination_hash
            document["account_profile_bindings"] = deepcopy(
                target_config.get("account_profile_bindings") or []
            )
    return document


def _apply_research_objectives(
    cfg: dict[str, Any],
    objectives: ResearchObjectivesV1,
    *,
    variant_id: str,
    today: date,
) -> list[dict[str, Any]]:
    """Freeze a missing objective contract without changing strategy mechanics."""

    if isinstance(cfg.get("research_objectives"), Mapping) or cfg.get(
        "research_objectives_sha256"
    ):
        raise ValueError(
            f"{variant_id} already declares frozen research objectives; they cannot be replaced"
        )
    if date.fromisoformat(objectives.development_deadline) < today:
        raise ValueError("research development deadline cannot be in the past")
    payload = objectives.model_dump(mode="json", by_alias=True)
    load_research_policy().validate_objectives(payload)
    objective_hash = _object_sha256(payload)
    old_tests = deepcopy(cfg.get("campaign_tests"))
    cfg["research_objectives"] = deepcopy(payload)
    cfg["research_objectives_sha256"] = objective_hash
    canonical = canonicalize_campaign_config(cfg)
    cfg.clear()
    cfg.update(canonical)
    changes = [
        {
            "variant_id": variant_id,
            "scope": "research_protocol",
            "field": "research_objectives",
            "old": None,
            "new": deepcopy(payload),
            "new_sha256": objective_hash,
            "reviewed": True,
        }
    ]
    if old_tests != cfg.get("campaign_tests"):
        changes.append(
            {
                "variant_id": variant_id,
                "scope": "repository_methodology",
                "field": "campaign_tests",
                "old": old_tests,
                "new": deepcopy(cfg.get("campaign_tests")),
                "reviewed": True,
            }
        )
    return changes


def _apply_destination_benchmarks(
    cfg: dict[str, Any],
    selections: list[DestinationBenchmarkSelectionV1],
    *,
    variant_id: str,
    project_root: Path,
    declared_at: datetime,
) -> list[dict[str, Any]]:
    """Freeze exact account profiles, costs, and promotion scope before PnL."""

    from alphaquest.accounts.catalog import resolve_account_profile

    if cfg.get("destination_benchmark_contract") or cfg.get(
        "destination_benchmark_contract_sha256"
    ):
        raise ValueError(
            f"{variant_id} already declares a destination benchmark contract"
        )
    if cfg.get("account_profile_bindings"):
        raise ValueError(
            f"{variant_id} already has account profile bindings; the legacy protocol "
            "action cannot replace them"
        )
    if declared_at.tzinfo is None or declared_at.utcoffset() is None:
        raise ValueError("destination benchmark declaration time must be timezone-aware")

    bindings: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    for selection in selections:
        resolved = resolve_account_profile(
            selection.profile_id,
            version=selection.profile_version,
            project_root=project_root,
        )
        profile = resolved.profile
        if not profile.promotable:
            raise ValueError(
                f"destination benchmark is not promotable: {profile.profile_id}@{profile.version}"
            )
        if resolved.sha256 != selection.profile_sha256:
            raise ValueError(
                f"destination profile hash drifted before declaration: "
                f"{profile.profile_id}@{profile.version}"
            )
        acquisition = profile.rules.acquisition
        costs_required = (
            acquisition.evaluation_price_mode == "assessment_input_required"
            or acquisition.activation_fee_mode == "assessment_input_required"
        )
        if costs_required and selection.costs is None:
            raise ValueError(
                f"{profile.profile_id}@{profile.version} requires frozen acquisition costs"
            )
        if not costs_required and selection.costs is not None:
            raise ValueError(
                f"{profile.profile_id}@{profile.version} does not accept acquisition costs"
            )
        costs = selection.costs
        if costs is not None:
            if costs.currency != profile.identity.currency:
                raise ValueError(
                    f"destination costs for {profile.profile_id} must use "
                    f"{profile.identity.currency}"
                )
            if costs.observed_at > declared_at:
                raise ValueError("destination benchmark costs cannot be observed in the future")

        snapshot = resolved.snapshot()
        snapshot["role"] = selection.role
        bindings.append(snapshot)
        profiles.append(
            {
                "profile_id": profile.profile_id,
                "profile_version": profile.version,
                "profile_sha256": resolved.sha256,
                "role": selection.role,
                "account_kind": profile.identity.account_kind,
                "provider": profile.identity.provider,
                "program": profile.identity.program,
                "account_label": profile.identity.account_label,
                "costs": costs.model_dump(mode="json") if costs else None,
                "success_requirements": profile.evaluation_policy.model_dump(
                    mode="json"
                ),
                "required_manual_attestations": list(
                    profile.rules.manual_attestations_required
                ),
                "benchmark_acknowledged": True,
            }
        )

    contract = {
        "schema": DESTINATION_BENCHMARK_SCHEMA,
        "declared_at": declared_at.isoformat(),
        "declared_pre_pnl": True,
        "scientific_validity_required": True,
        "generic_objective_pass_required": False,
        "approval_scope": "exact_primary_profile_only",
        "profiles": profiles,
        "confirmed": True,
    }
    contract_hash = _object_sha256(contract)
    cfg["account_profile_bindings"] = bindings
    cfg["destination_benchmark_contract"] = contract
    cfg["destination_benchmark_contract_sha256"] = contract_hash
    return [
        {
            "variant_id": variant_id,
            "scope": "destination_benchmark",
            "field": "destination_benchmark_contract",
            "old": None,
            "new": deepcopy(contract),
            "new_sha256": contract_hash,
            "reviewed": True,
        }
    ]


def _require_full_methodology(cfg: Mapping[str, Any]) -> None:
    tests = cfg.get("campaign_tests")
    if not isinstance(tests, Mapping):
        raise ValueError("follow-up configs require the full campaign_tests methodology")
    if list(tests.get("stage_order") or []) != list(DEFAULT_STAGE_ORDER):
        raise ValueError(
            "follow-up stage_order must contain the full mandatory methodology in order: "
            + ", ".join(DEFAULT_STAGE_ORDER)
        )
    missing = [
        stage
        for stage in DEFAULT_STAGE_ORDER
        if not isinstance(tests.get(stage), Mapping) or tests[stage].get("enabled") is not True
    ]
    if missing:
        raise ValueError("follow-up mandatory stages are missing or disabled: " + ", ".join(missing))


def _attempt_has_performance_evidence(
    evidence_roots: tuple[Path, ...],
    runtime_root: Path,
    project_root: Path,
    campaign_id: str,
    attempt_id: str,
    configs: Mapping[str, Mapping[str, Any]],
    config_paths: Mapping[str, Path],
) -> bool:
    expected_runs = {
        _expected_run_dir(evidence_root, campaign_id, variant_id, cfg)
        for evidence_root in evidence_roots
        for variant_id, cfg in configs.items()
    }
    existing_runs = {path for path in expected_runs if path.exists()}
    proven_pre_performance_runs = {
        path for path in existing_runs if _is_proven_pre_performance_incomplete_run(path, attempt_id)
    }
    if existing_runs - proven_pre_performance_runs:
        return True

    for evidence_root in evidence_roots:
        campaign_root = evidence_root / campaign_id
        if not campaign_root.is_dir():
            continue
        for pattern in ("**/campaign_test_summary.json", "**/studio_incomplete_attempt.json"):
            for path in campaign_root.glob(pattern):
                if str(_read_json(path).get("attempt_id") or "") == attempt_id:
                    if not _is_proven_pre_performance_incomplete_run(path.parent, attempt_id):
                        return True

    database = runtime_root / "jobs.sqlite3"
    if database.is_file():
        queue = SQLiteJobQueue(database)
        for job in queue.list_jobs(limit=100_000):
            if (
                job.job_type == "campaign_variant_run"
                and job.campaign_id == campaign_id
                and str(job.payload.get("attempt_id") or "") == attempt_id
                and (
                    job.state.value in {"QUEUED", "RUNNING", "CANCEL_REQUESTED"}
                    or (job.attempt_reserved and not proven_pre_performance_runs)
                )
            ):
                return True

    config_sources = {path.resolve() for path in config_paths.values()}
    recovery_root = runtime_root / "recovery"
    for journal_path in recovery_root.glob("*.json") if recovery_root.is_dir() else []:
        journal = _read_json(journal_path)
        events = journal.get("events") if isinstance(journal.get("events"), list) else []
        reserved = any(
            isinstance(event, Mapping) and str(event.get("phase") or "") in {"ATTEMPT_RESERVED", "ATTEMPT_INCOMPLETE"}
            for event in events
        )
        if not reserved:
            continue
        for event in events:
            details = event.get("details") if isinstance(event, Mapping) else None
            if not isinstance(details, Mapping):
                continue
            output = _resolved_recorded_path(details.get("output_dir"), project_root)
            source = _resolved_recorded_path(details.get("config_path"), project_root)
            if output in expected_runs or source in config_sources:
                if output not in proven_pre_performance_runs:
                    return True
    return False


def _is_proven_pre_performance_incomplete_run(run_dir: Path, attempt_id: str) -> bool:
    """Recognize a terminal run that stopped before any PnL-bearing stage began."""

    if not run_dir.is_dir():
        return False
    summary_path = run_dir / "campaign_test_summary.json"
    incomplete_path = run_dir / "studio_incomplete_attempt.json"
    if not summary_path.is_file() or not incomplete_path.is_file():
        return False
    summary = _read_json(summary_path)
    incomplete = _read_json(incomplete_path)
    if (
        str(summary.get("attempt_id") or "") != attempt_id
        or str(incomplete.get("attempt_id") or "") != attempt_id
        or summary.get("status") != "incomplete"
        or summary.get("halted") is not True
        or summary.get("stages") != []
        or incomplete.get("attempt_reserved") is not True
        or incomplete.get("operational_state") not in {"FAILED_OPERATIONAL", "CANCELLED"}
    ):
        return False
    allowed_files = {
        "campaign_test_summary.json",
        "effective_config.yaml",
        "source_config.yaml",
        "studio_incomplete_attempt.json",
        "variant.yaml",
    }
    return all(
        path.parent == run_dir and path.name in allowed_files
        for path in run_dir.rglob("*")
        if path.is_file()
    )


def _attempt_variant_failed(
    evidence_roots: tuple[Path, ...],
    campaign_id: str,
    variant_id: str,
    attempt_id: str,
    config: Mapping[str, Any],
    config_path: Path,
) -> bool:
    for evidence_root in evidence_roots:
        run_dir = _expected_run_dir(evidence_root, campaign_id, variant_id, config)
        bundle_path = run_dir / REPORTING_DIRECTORY / RESULT_BUNDLE_FILENAME
        if not bundle_path.is_file():
            continue
        inspection = inspect_finalized_result(bundle_path, config_path=config_path)
        bundle = inspection.get("bundle")
        if (
            inspection.get("valid") is True
            and bundle is not None
            and bundle.campaign_id == campaign_id
            and bundle.variant_id == variant_id
            and bundle.run_id == str(config.get("test_run_id") or "")
            and bundle.verdict == "FAIL"
            and str(config.get("attempt_id") or "") == attempt_id
        ):
            return True
    return False


def _expected_run_dir(
    evidence_root: Path,
    campaign_id: str,
    variant_id: str,
    config: Mapping[str, Any],
) -> Path:
    data = config.get("data") if isinstance(config.get("data"), Mapping) else {}
    symbol = str(config.get("symbol") or data.get("symbol") or "")
    run_id = str(config.get("test_run_id") or "")
    if not symbol or not run_id:
        raise ValueError(f"{variant_id} does not declare symbol and test_run_id for evidence lineage")
    return (evidence_root / campaign_id / variant_id / symbol / run_id).resolve()


def _resolved_recorded_path(value: Any, project_root: Path) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return (path if path.is_absolute() else project_root / path).resolve()


def _refresh_and_require_unique_mechanic_signatures(configs: Mapping[str, dict[str, Any]]) -> None:
    signatures: dict[str, str] = {}
    for variant_id, cfg in configs.items():
        signature = _config_mechanic_signature(cfg)
        research = cfg.setdefault("research_metadata", {})
        if not isinstance(research, dict):
            raise ValueError(f"{variant_id} research_metadata must be a mapping")
        research["mechanic_signature"] = signature
        signatures[variant_id] = signature
    _require_unique_mechanic_signatures(signatures)


def _require_unique_mechanic_signatures(signatures: Mapping[str, str]) -> None:
    if not 1 <= len(signatures) <= 5 or len(set(signatures.values())) != len(signatures):
        duplicates = sorted(
            variant for variant, signature in signatures.items() if list(signatures.values()).count(signature) > 1
        )
        detail = ", ".join(duplicates) if duplicates else "invalid variant count"
        raise ValueError(
            "all follow-up variants must retain materially distinct, value-independent mechanics; "
            f"duplicate signatures: {detail}"
        )


def _config_mechanic_signature(config: Mapping[str, Any]) -> str:
    strategy = config.get("strategy")
    if not isinstance(strategy, Mapping):
        raise ValueError("strategy must be a mapping before computing mechanic_signature")
    structural: dict[str, Any] = {}
    for config_name, signature_name in (("entry", "entry"), ("sl", "stop"), ("tp", "target")):
        component = strategy.get(config_name)
        if not isinstance(component, Mapping):
            raise ValueError(f"strategy.{config_name} must be a mapping before computing mechanic_signature")
        module = str(component.get("module") or "")
        params = component.get("params") if isinstance(component.get("params"), Mapping) else {}
        binding: dict[str, Any] = {"module": module, "module_type": signature_name}
        if module == "safe_bar_rule" and isinstance(params.get("rule"), Mapping):
            binding["rule"] = _strip_rule_values(params["rule"])
        elif module == "daily_time_series_momentum":
            binding["setup_mode"] = params.get("setup_mode", "close_to_close_trend")
        structural[signature_name] = binding
    encoded = json.dumps(structural, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _strip_rule_values(value: Any) -> Any:
    if isinstance(value, list):
        return [_strip_rule_values(item) for item in value]
    if not isinstance(value, Mapping):
        return "<value>"
    source = value.get("source")
    if source == "constant":
        return {"source": "constant", "value_type": type(value.get("value")).__name__}
    if source == "tunable":
        return {"source": "tunable"}
    ignored = {"values", "default", "signal_start_time", "signal_end_time", "bar_interval_minutes"}
    return {key: _strip_rule_values(item) for key, item in sorted(value.items()) if key not in ignored}


def _attempt_test_data_windows(
    cfg: Mapping[str, Any],
    *,
    project_root: Path,
    evidence_root: Path,
) -> list[dict[str, Any]]:
    try:
        rows = campaign_test_data_window_plan(dict(cfg))
    except (KeyError, TypeError, ValueError) as exc:
        return [
            {
                "stage": "window_plan",
                "label": "Test data windows",
                "status": "unavailable",
                "detail": f"Planned windows could not be resolved: {exc}",
            }
        ]

    by_stage = {str(item.get("stage") or ""): item for item in rows}
    _merge_mechanics_window_evidence(
        by_stage.get("mechanics_validation"),
        cfg,
        project_root=project_root,
    )
    run_root = (
        evidence_root
        / str(cfg.get("campaign_id") or "")
        / str(cfg.get("variant_id") or "")
        / str(cfg.get("symbol") or (cfg.get("data") or {}).get("symbol") or "")
        / str(cfg.get("test_run_id") or "")
    )
    summaries = {
        "limited_core_grid_test": run_root / "limited_core_grid_test" / "core_grid_summary.json",
        "limited_monkey_test": run_root / "limited_monkey_test" / "monkey_summary.json",
        "walk_forward_analysis": run_root / "walk_forward_analysis" / "wfa_summary.json",
        "simulated_incubation_core": (
            run_root / "simulated_incubation_core" / "incubation_oos_summary.json"
        ),
        "acceptance_oos_test": (
            run_root / "acceptance_oos_test" / "acceptance_oos_summary.json"
        ),
    }
    loaded: dict[str, dict[str, Any]] = {}
    for stage, path in summaries.items():
        if not path.is_file() or stage not in by_stage:
            continue
        try:
            summary = _read_json(path)
        except ValueError:
            continue
        loaded[stage] = summary
        _merge_stage_window_summary(by_stage[stage], summary, path)

    wfa_results = run_root / "walk_forward_analysis" / "wfa_results.csv"
    wfa_period = _csv_column_period(wfa_results, "test_start", "test_end")
    if wfa_period is not None:
        for stage in ("wfa_oos_monkey_test", "wfa_oos_monte_carlo"):
            row = by_stage.get(stage)
            if row is not None:
                row.update(
                    {
                        "actual_start": wfa_period["start"],
                        "actual_end": wfa_period["end"],
                        "actual_windows": wfa_period["rows"],
                        "status": "actual",
                        "summary_path": str(wfa_results),
                    }
                )

    incubation = loaded.get("simulated_incubation_core")
    if incubation:
        row = by_stage.get("simulated_incubation_monkey")
        if row is not None:
            row.update(
                {
                    "actual_start": incubation.get("test_start"),
                    "actual_end": incubation.get("test_end"),
                    "status": "actual",
                    "summary_path": str(summaries["simulated_incubation_core"]),
                }
            )
    return rows


def _merge_mechanics_window_evidence(
    row: dict[str, Any] | None,
    cfg: Mapping[str, Any],
    *,
    project_root: Path,
) -> None:
    if row is None:
        return
    gate = ((cfg.get("research_metadata") or {}).get("validation_gate") or {})
    evidence_value = gate.get("evidence_dir")
    if not evidence_value:
        return
    evidence_dir = Path(str(evidence_value))
    if not evidence_dir.is_absolute():
        evidence_dir = (project_root / evidence_dir).resolve()
    metadata_path = evidence_dir / "metadata.json"
    if not metadata_path.is_file():
        return
    try:
        metadata = _read_json(metadata_path)
    except ValueError:
        return
    source_value = metadata.get("source_run_dir")
    source_run = Path(str(source_value)) if source_value else None
    if source_run is not None and not source_run.is_absolute():
        source_run = (project_root / source_run).resolve()
    metrics_path = source_run / "metrics.json" if source_run is not None else None
    if metrics_path is not None and metrics_path.is_file():
        try:
            metrics = _read_json(metrics_path)
        except ValueError:
            metrics = {}
        subset = metrics.get("data_subset") if isinstance(metrics.get("data_subset"), Mapping) else {}
        row["resolved_start"] = subset.get("start_date") or subset.get("start_timestamp")
        row["resolved_end"] = subset.get("end_date") or subset.get("end_timestamp")
    audits_path = source_run / "session_audits.csv" if source_run is not None else None
    if audits_path is not None:
        period = _csv_column_period(audits_path, "session_date", "session_date")
        if period is not None:
            row.update(
                {
                    "actual_start": period["start"],
                    "actual_end": period["end"],
                    "actual_sessions": period["rows"],
                    "status": "actual",
                    "summary_path": str(metadata_path),
                }
            )


def _merge_stage_window_summary(
    row: dict[str, Any],
    summary: Mapping[str, Any],
    path: Path,
) -> None:
    resolved = (
        summary.get("resolved_data_subset")
        if isinstance(summary.get("resolved_data_subset"), Mapping)
        else summary.get("data_subset")
        if isinstance(summary.get("data_subset"), Mapping)
        else {}
    )
    actual = (
        summary.get("actual_data_period")
        if isinstance(summary.get("actual_data_period"), Mapping)
        else {}
    )
    row.update(
        {
            "resolved_start": resolved.get("start_date") or resolved.get("start_timestamp"),
            "resolved_end": resolved.get("end_date") or resolved.get("end_timestamp"),
            "actual_start": actual.get("first_timestamp"),
            "actual_end": actual.get("last_timestamp"),
            "actual_rows": actual.get("strategy_rows") or actual.get("rows"),
            "status": "actual" if actual.get("first_timestamp") else "resolved",
            "summary_path": str(path),
        }
    )
    for key in ("train_start", "train_end", "test_start", "test_end"):
        if summary.get(key) is not None:
            row[key] = summary.get(key)


def _csv_column_period(path: Path, start_column: str, end_column: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    starts: list[str] = []
    ends: list[str] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for item in csv.DictReader(handle):
                start = str(item.get(start_column) or "").strip()
                end = str(item.get(end_column) or "").strip()
                if start and end:
                    starts.append(start)
                    ends.append(end)
    except OSError:
        return None
    if not starts:
        return None
    return {
        "start": min(starts),
        "end": max(ends),
        "rows": len(starts),
    }


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"could not read YAML mapping {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"YAML document must be a mapping: {path}")
    return value


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read JSON mapping {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must be a mapping: {path}")
    return value


def _write_yaml(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(dict(value), sort_keys=False, width=120), encoding="utf-8")


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(value), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def _restore_bytes(path: Path, previous: bytes | None) -> None:
    if previous is None:
        path.unlink(missing_ok=True)
        return
    temporary = path.with_name(f".{path.name}.follow-up-rollback")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_bytes(previous)
    os.replace(temporary, path)


__all__ = [
    "ATTEMPT_KINDS",
    "DESTINATION_BENCHMARK_SCHEMA",
    "DestinationBenchmarkSelectionV1",
    "FOLLOW_UP_SCHEMA",
    "FollowUpAttemptRequestV1",
    "FollowUpAttemptResult",
    "FollowUpAttemptService",
    "MechanicParameterPatchV1",
]
