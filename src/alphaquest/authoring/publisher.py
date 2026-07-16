from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

import yaml

from alphaquest.authoring.compiler import CompiledCampaign
from alphaquest.research.schemas import validate_campaign_config_contract


class CampaignPublishError(RuntimeError):
    """Raised when an authored tree cannot be installed without partial state."""


@dataclass(frozen=True)
class PublishResult:
    campaign_id: str
    destination: Path
    files: tuple[Path, ...]
    file_sha256: Mapping[str, str]
    draft_sha256: str


class TransactionalCampaignPublisher:
    """Write and atomically install one compiled campaign source tree.

    Repository preflight runs against all five staged configs by default.
    Duplicate scanning and any additional repository refresh checks can be
    supplied as read-only callbacks; every check completes before the single
    atomic rename.
    """

    def __init__(
        self,
        *,
        project_root: str | Path = ".",
        active_campaign_root: str | Path = "research/campaigns/active",
        duplicate_guard: Callable[[Any], None] | None = None,
        staged_validator: Callable[[Path], None] | None = None,
        repository_preflight: bool = True,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        source_root = Path(active_campaign_root)
        self.active_campaign_root = (
            source_root.resolve() if source_root.is_absolute() else (self.project_root / source_root).resolve()
        )
        try:
            self.active_campaign_root.relative_to(self.project_root)
        except ValueError as exc:
            raise ValueError("active_campaign_root must be inside project_root") from exc
        self.duplicate_guard = duplicate_guard
        self.staged_validator = staged_validator
        self.repository_preflight = bool(repository_preflight)

    def publish(self, compiled: CompiledCampaign) -> PublishResult:
        self._verify_compiled_hash(compiled)
        if self.duplicate_guard is not None:
            self.duplicate_guard(compiled.draft.model_copy(deep=True))

        self.active_campaign_root.mkdir(parents=True, exist_ok=True)
        destination = self.active_campaign_root / compiled.campaign_id
        if destination.exists() or destination.is_symlink():
            raise CampaignPublishError(f"campaign destination already exists: {destination}")
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{compiled.campaign_id}.publish-",
                dir=self.active_campaign_root,
            )
        )
        installed = False
        try:
            self._write_tree(staging, compiled)
            self._validate_tree(staging, compiled)
            if self.repository_preflight:
                _run_repository_preflight(staging, project_root=self.project_root)
            if self.staged_validator is not None:
                self.staged_validator(staging)
            hashes = _tree_hashes(staging)
            _fsync_tree(staging)
            os.replace(staging, destination)
            installed = True
            _fsync_directory(self.active_campaign_root)
        except Exception as exc:
            if not installed:
                shutil.rmtree(staging, ignore_errors=True)
            if isinstance(exc, CampaignPublishError):
                raise
            raise CampaignPublishError(f"campaign publication failed before atomic install: {exc}") from exc

        files = tuple(sorted(path for path in destination.rglob("*") if path.is_file()))
        return PublishResult(
            campaign_id=compiled.campaign_id,
            destination=destination,
            files=files,
            file_sha256=hashes,
            draft_sha256=compiled.draft_sha256,
        )

    def validate(self, compiled: CompiledCampaign) -> dict[str, str]:
        """Run the exact pre-install checks in a disposable staged tree."""

        self._verify_compiled_hash(compiled)
        if self.duplicate_guard is not None:
            self.duplicate_guard(compiled.draft.model_copy(deep=True))
        self.active_campaign_root.mkdir(parents=True, exist_ok=True)
        destination = self.active_campaign_root / compiled.campaign_id
        if destination.exists() or destination.is_symlink():
            raise CampaignPublishError(f"campaign destination already exists: {destination}")
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{compiled.campaign_id}.preflight-",
                dir=self.active_campaign_root,
            )
        )
        try:
            self._write_tree(staging, compiled)
            self._validate_tree(staging, compiled)
            if self.repository_preflight:
                _run_repository_preflight(staging, project_root=self.project_root)
            if self.staged_validator is not None:
                self.staged_validator(staging)
            return _tree_hashes(staging)
        except Exception as exc:
            if isinstance(exc, CampaignPublishError):
                raise
            raise CampaignPublishError(f"campaign pre-publication validation failed: {exc}") from exc
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _verify_compiled_hash(self, compiled: CompiledCampaign) -> None:
        draft = compiled.draft.model_dump(mode="json", by_alias=True)
        current = hashlib.sha256(
            json.dumps(draft, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        if current != compiled.draft_sha256:
            raise CampaignPublishError("compiled draft changed after review; recompile before publishing")
        manifest_hash = compiled.authoring_manifest.get("draft_sha256")
        if manifest_hash != current:
            raise CampaignPublishError("authoring manifest draft hash does not match compiled draft")
        expected_documents = compiled.authoring_manifest.get("compiled_document_sha256")
        if not isinstance(expected_documents, Mapping):
            raise CampaignPublishError("authoring manifest lacks compiled document hashes")
        current_documents = {
            "campaign.yaml": _object_sha256(compiled.campaign),
            "strategy_spec.yaml": _object_sha256(compiled.strategy_spec),
            **{
                f"variants/{variant_id}/config.yaml": _object_sha256(config)
                for variant_id, config in compiled.variant_configs.items()
            },
        }
        if dict(expected_documents) != current_documents:
            raise CampaignPublishError("compiled campaign documents changed after review; recompile before publishing")

    def _write_tree(self, root: Path, compiled: CompiledCampaign) -> None:
        _write_yaml(root / "campaign.yaml", compiled.campaign)
        _write_yaml(root / "strategy_spec.yaml", compiled.strategy_spec)
        _write_json(root / "authoring_manifest.json", compiled.authoring_manifest)
        for variant_id, config in compiled.variant_configs.items():
            _write_yaml(root / "variants" / variant_id / "config.yaml", config)

    def _validate_tree(self, root: Path, compiled: CompiledCampaign) -> None:
        files = {
            str(path.relative_to(root))
            for path in root.rglob("*")
            if path.is_file()
        }
        expected = set(compiled.relative_paths)
        if files != expected:
            raise CampaignPublishError(
                f"staged file set differs from compiled manifest; expected={sorted(expected)}, actual={sorted(files)}"
            )
        if any(path.suffix == ".py" for path in root.rglob("*")):
            raise CampaignPublishError("Studio publication must not generate Python strategy stubs")
        campaign = _read_yaml(root / "campaign.yaml")
        if campaign.get("campaign_id") != compiled.campaign_id:
            raise CampaignPublishError("staged campaign ID changed during serialization")
        declared = list(campaign.get("variants") or [])
        if declared != list(compiled.variant_configs):
            raise CampaignPublishError("campaign variant order does not match compiled configs")
        for variant_id in declared:
            config_path = root / "variants" / variant_id / "config.yaml"
            config = _read_yaml(config_path)
            validate_campaign_config_contract(config, context=str(config_path))
            if config.get("campaign_id") != compiled.campaign_id or config.get("variant_id") != variant_id:
                raise CampaignPublishError(f"identity mismatch in {config_path}")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _write_yaml(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(_plain(value), sort_keys=False, default_flow_style=False, width=120),
        encoding="utf-8",
    )


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_plain(value), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _read_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise CampaignPublishError(f"expected mapping in {path}")
    return value


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _object_sha256(value: Any) -> str:
    encoded = json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _run_repository_preflight(staged_campaign_root: Path, *, project_root: Path) -> None:
    from alphaquest.research.preflight import run_preflight

    configs = sorted(staged_campaign_root.glob("variants/*/config.yaml"))
    result = run_preflight(config_paths=configs, run_tests=False, project_root=project_root)
    if result.get("passed") is True:
        return
    failures = [str(item) for item in result.get("failures") or []]
    detail = "; ".join(failures[:10]) or "preflight returned no diagnostic"
    raise CampaignPublishError(f"repository preflight rejected staged campaign: {detail}")


def _fsync_tree(root: Path) -> None:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            with path.open("rb") as handle:
                os.fsync(handle.fileno())
    for directory in sorted((path for path in root.rglob("*") if path.is_dir()), reverse=True):
        _fsync_directory(directory)
    _fsync_directory(root)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


__all__ = [
    "CampaignPublishError",
    "PublishResult",
    "TransactionalCampaignPublisher",
]
