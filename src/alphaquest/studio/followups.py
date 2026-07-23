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
from datetime import UTC, datetime, time
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
from typing import Any, Callable, Literal, Mapping
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import yaml

from alphaquest.authoring.catalog import CERTIFIED_MODULE_CATALOG
from alphaquest.authoring.compiler import (
    AUTHORING_MANIFEST_SCHEMA,
    STRATEGY_SPEC_SCHEMA,
    mechanics_validation_subset,
)
from alphaquest.authoring.models import DatasetManifestV1, ModuleBindingV1
from alphaquest.research.definitions import write_definition_manifests
from alphaquest.research.campaign_stages import (
    DEFAULT_STAGE_ORDER,
    campaign_test_data_window_plan,
)
from alphaquest.research.preflight import run_preflight
from alphaquest.research.schemas import validate_campaign_config_contract
from alphaquest.research.storage import load_storage_layout
from alphaquest.studio.approvals import require_all_variant_mechanics_approved
from alphaquest.studio.finalization import REPORTING_DIRECTORY, inspect_finalized_result
from alphaquest.studio.jobs import JobRecordV1, SQLiteJobQueue
from alphaquest.studio.ledger import append_planned_follow_up
from alphaquest.studio.results import RESULT_BUNDLE_FILENAME
from alphaquest.studio.workspace import refresh_generated_indexes_if_stale
from alphaquest.strategy_certification import (
    StrategyCertificationError,
    get_strategy_certification,
    normalize_certified_event_params,
    strategy_identity_for_config,
    validate_certified_event_parameter_grid,
)
from alphaquest.validation.promotion_gate import inspect_validation_gate


FOLLOW_UP_SCHEMA = "alphaquest.follow-up-attempt/v1"
FOLLOW_UP_ROOT = "follow_up_attempts"
ATTEMPT_KINDS = (
    "replication",
    "data_refresh",
    "methodology_rerun",
    "pre_pnl_mechanics_correction",
    "pre_pnl_parameter_declaration",
    "rescue",
)
AttemptKind = Literal[
    "replication",
    "data_refresh",
    "methodology_rerun",
    "pre_pnl_mechanics_correction",
    "pre_pnl_parameter_declaration",
    "rescue",
]
JsonScalar = str | int | float | bool | None


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
    parameter_grid: dict[str, list[JsonScalar]] = Field(default_factory=dict)

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
        if self.attempt_kind == "data_refresh" and not self.dataset_id:
            raise ValueError("data_refresh requires a governed dataset_id")
        if self.attempt_kind != "data_refresh" and self.dataset_id is not None:
            raise ValueError("dataset_id is only valid for data_refresh")
        if mechanics_kind and (not self.target_variant_id or not self.mechanic_patches):
            raise ValueError(f"{self.attempt_kind} requires a target variant and an explicit mechanics patch")
        if declaration_kind and (not self.target_variant_id or not self.parameter_grid):
            raise ValueError("pre_pnl_parameter_declaration requires a target variant and parameter grid")
        if not (mechanics_kind or declaration_kind) and (
            self.target_variant_id is not None or self.mechanic_patches or self.parameter_grid
        ):
            raise ValueError(
                "target_variant_id, mechanic_patches, and parameter_grid are only valid for governed mechanics changes"
            )
        if declaration_kind and self.mechanic_patches:
            raise ValueError("parameter declaration cannot also patch fixed mechanics")
        if mechanics_kind and self.parameter_grid:
            raise ValueError("mechanics correction and rescue cannot also redeclare the parameter grid")
        if self.target_variant_id and any(
            patch.variant_id != self.target_variant_id for patch in self.mechanic_patches
        ):
            raise ValueError("every mechanics patch must target the declared target_variant_id")
        if self.attempt_kind == "rescue" and not self.authorized_by:
            raise ValueError("rescue requires an explicitly identified authorizer")
        if self.attempt_kind != "rescue" and self.authorized_by is not None:
            raise ValueError("authorized_by is reserved for the governed rescue lane")
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
        parent_path_by_variant = {path.parent.name: path for path in parent_paths}
        parent_configs = {path.parent.name: _read_yaml(path) for path in parent_paths}
        if tuple(parent_configs) != variants:
            parent_configs = {
                variant: _read_yaml(next(path for path in parent_paths if path.parent.name == variant))
                for variant in variants
            }
            parent_path_by_variant = {
                variant: next(path for path in parent_paths if path.parent.name == variant) for variant in variants
            }
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
        configs = {variant: deepcopy(parent_configs[variant]) for variant in variants}
        dataset_manifest = self._dataset_for_configs(configs)
        changes: list[dict[str, Any]] = []

        if parsed.attempt_kind == "data_refresh":
            dataset_manifest = self._load_dataset(str(parsed.dataset_id))
            for variant in variants:
                changes.extend(
                    _apply_dataset_refresh(
                        configs[variant],
                        dataset_manifest,
                        variant_id=variant,
                        project_root=self.project_root,
                    )
                )
        elif parsed.attempt_kind in {"pre_pnl_mechanics_correction", "rescue"}:
            assert parsed.target_variant_id is not None
            target = configs[parsed.target_variant_id]
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

        created_at = self._now()
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ValueError("follow-up attempt clock must return a timezone-aware datetime")
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
            self._validate_certified_mechanics(cfg, dataset_manifest)
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
            preflight = run_preflight(
                config_paths=staged_paths,
                run_tests=False,
                project_root=self.project_root,
            )
            if not bool(preflight.get("passed")):
                failures = "; ".join(str(item) for item in preflight.get("failures") or [])
                raise ValueError(f"follow-up preflight failed before installation: {failures}")
            config_hashes = {variant: _file_sha256(path) for variant, path in zip(variants, staged_paths)}
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
                "dataset_id": dataset_manifest.dataset_id,
                "dataset_manifest_sha256": _file_sha256(
                    self.layout.dataset_root / dataset_manifest.dataset_id / "dataset_manifest.json"
                ),
                "changes": changes,
                "preflight": {
                    "verdict": "PASS",
                    "config_count": len(staged_paths),
                    "warnings": [str(item) for item in preflight.get("warnings") or []],
                },
                "immutable": True,
                "automatic_replay_permitted": False,
                "ledger_event_stage": f"follow_up_attempt/{attempt_id}",
            }
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
                dataset_id=dataset_manifest.dataset_id,
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

    def queue_mechanics_validation(
        self,
        campaign_id: str,
        attempt_id: str,
    ) -> list[JobRecordV1]:
        from alphaquest.studio.worker import MECHANICS_VALIDATION_RUN

        paths = self.config_paths(campaign_id, attempt_id)[-1:]
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
            jobs.append(
                queue.submit(
                    job_type=MECHANICS_VALIDATION_RUN,
                    campaign_id=campaign_id,
                    payload={
                        "campaign_id": campaign_id,
                        "variant_id": str(cfg["variant_id"]),
                        "attempt_id": attempt_id,
                        "config_path": str(config_path),
                    },
                    idempotency_key=(
                        f"{campaign_id}:{cfg['variant_id']}:{attempt_id}:mechanics_validation:"
                        f"{config_hash}:{data_hash}"
                    ),
                    hash_locks={"config_hash": config_hash, "input_data_hash": data_hash},
                )
            )
        return jobs

    def queue_performance(self, campaign_id: str, attempt_id: str) -> list[JobRecordV1]:
        paths = self.config_paths(campaign_id, attempt_id)[-1:]
        approvals = require_all_variant_mechanics_approved(list(paths))
        gates = {Path(str(item["config_path"])).resolve(): item for item in approvals}
        queue = SQLiteJobQueue(self.layout.studio_runtime_root / "jobs.sqlite3")
        jobs: list[JobRecordV1] = []
        for config_path in paths:
            cfg = _read_yaml(config_path)
            gate = gates[config_path.resolve()]
            output_dir = (
                self.layout.evidence_roots[0]
                / campaign_id
                / str(cfg["variant_id"])
                / str(cfg.get("symbol") or (cfg.get("data") or {}).get("symbol"))
                / str(cfg["test_run_id"])
            )
            jobs.append(
                queue.submit(
                    job_type="campaign_variant_run",
                    campaign_id=campaign_id,
                    payload={
                        "campaign_id": campaign_id,
                        "variant_id": str(cfg["variant_id"]),
                        "attempt_id": attempt_id,
                        "config_path": str(config_path),
                        "output_dir": str(output_dir),
                    },
                    idempotency_key=f"{campaign_id}:{cfg['variant_id']}:{attempt_id}",
                    hash_locks={
                        "config_hash": str(gate.get("config_hash") or ""),
                        "input_data_hash": str(gate.get("input_data_hash") or ""),
                    },
                )
            )
        return jobs

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
        canonical = Path(manifest.path)
        canonical = canonical if canonical.is_absolute() else self.project_root / canonical
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
                artifact = Path(str(value))
                artifact = artifact if artifact.is_absolute() else self.project_root / artifact
                if not artifact.is_file() or _file_sha256(artifact) != event.get(hash_field):
                    raise ValueError(f"governed event-source artifact is missing or hash-drifted: {field}")
            raw_dir = event.get("raw_dir")
            if raw_dir:
                directory = Path(str(raw_dir))
                directory = directory if directory.is_absolute() else self.project_root / directory
                if not directory.is_dir():
                    raise ValueError("governed Sierra raw_dir is missing")
        return manifest

    def _dataset_for_configs(self, configs: Mapping[str, Mapping[str, Any]]) -> DatasetManifestV1:
        ids = {
            str(cfg.get("dataset_id") or (cfg.get("data") or {}).get("dataset_id") or "") for cfg in configs.values()
        }
        if len(ids) != 1 or not next(iter(ids)):
            raise ValueError("all parent configs must use one governed dataset")
        return self._load_dataset(next(iter(ids)))

    def _validate_certified_mechanics(
        self,
        cfg: dict[str, Any],
        dataset: DatasetManifestV1,
    ) -> None:
        if cfg.get("symbol") != dataset.symbol or cfg.get("timeframe") != dataset.timeframe:
            raise ValueError("follow-up dataset symbol and timeframe must match the frozen campaign")
        strategy = cfg.get("strategy") if isinstance(cfg.get("strategy"), dict) else {}
        if str(cfg.get("engine_lane") or "") == "canonical_event_replay":
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
    )
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


def _attempt_strategy_spec(
    request: FollowUpAttemptRequestV1,
    attempt_id: str,
    created_at: datetime,
    configs: Mapping[str, Mapping[str, Any]],
    changes: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
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
    if any(path.exists() for path in expected_runs):
        return True

    for evidence_root in evidence_roots:
        campaign_root = evidence_root / campaign_id
        if not campaign_root.is_dir():
            continue
        for pattern in ("**/campaign_test_summary.json", "**/studio_incomplete_attempt.json"):
            for path in campaign_root.glob(pattern):
                if str(_read_json(path).get("attempt_id") or "") == attempt_id:
                    return True

    database = runtime_root / "jobs.sqlite3"
    if database.is_file():
        queue = SQLiteJobQueue(database)
        for job in queue.list_jobs(limit=100_000):
            if (
                job.job_type == "campaign_variant_run"
                and job.campaign_id == campaign_id
                and str(job.payload.get("attempt_id") or "") == attempt_id
                and (job.attempt_reserved or job.state.value in {"QUEUED", "RUNNING", "CANCEL_REQUESTED"})
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
                return True
    return False


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
    "FOLLOW_UP_SCHEMA",
    "FollowUpAttemptRequestV1",
    "FollowUpAttemptResult",
    "FollowUpAttemptService",
    "MechanicParameterPatchV1",
]
