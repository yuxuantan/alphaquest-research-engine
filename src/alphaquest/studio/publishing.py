"""End-to-end, recovery-journaled Studio campaign publication."""

from __future__ import annotations

import csv
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import threading
from typing import Any
from uuid import uuid4

from alphaquest.authoring import CampaignCompiler, CampaignDraftV1, PublishResult, TransactionalCampaignPublisher
from alphaquest.authoring.models import DatasetManifestV1
from alphaquest.research.storage import display_path, load_storage_layout
from alphaquest.studio.duplicates import duplicate_matches
from alphaquest.studio.ledger import LEDGER_FIELDS, append_planned_publication
from alphaquest.studio.workspace import refresh_generated_indexes_if_stale


_PUBLICATION_LOCK = threading.Lock()


@dataclass(frozen=True)
class StudioPublishResult:
    campaign_id: str
    destination: Path
    files: tuple[Path, ...]
    file_sha256: dict[str, str]
    draft_sha256: str
    ledger_rows_appended: int
    indexes_refreshed: bool
    journal_path: Path
    verdict: str = "PASS"


class StudioPublicationService:
    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        self.layout = load_storage_layout(self.project_root)
        self.journal_root = self.layout.studio_runtime_root / "publication-journal"
        self.lock_path = self.layout.studio_runtime_root / "publication.lock"

    def publish(self, draft: CampaignDraftV1) -> StudioPublishResult:
        if not isinstance(draft, CampaignDraftV1):
            draft = CampaignDraftV1.model_validate(draft)
        self._require_governed_dataset_manifest(draft)
        self._recheck_dataset_hash(draft)
        compiled = self._compiler().compile(draft)
        published: PublishResult | None = None
        rows = 0
        refresh: dict[str, Any] = {}
        with _publication_file_lock(self.lock_path), _working_directory(self.project_root):
            self._recover_preparing_locked()
            destination = (self.layout.active_campaign_root / draft.campaign_id).resolve()
            if destination.exists() or destination.is_symlink():
                raise FileExistsError(f"campaign destination already exists: {destination}")
            transaction_id = uuid4().hex
            journal_path = self.journal_root / f"{draft.campaign_id}.{transaction_id}.json"
            ledger_path = self.project_root / "research_ledger.csv"
            backup_path = self.journal_root / f"{draft.campaign_id}.{transaction_id}.ledger.bak"
            ledger_snapshot = _persist_ledger_backup(ledger_path, backup_path)
            journal = {
                "schema": "alphaquest.studio-publication-journal/v1",
                "transaction_id": transaction_id,
                "campaign_id": draft.campaign_id,
                "draft_sha256": compiled.draft_sha256,
                "destination": display_path(destination, self.project_root),
                "ledger_path": display_path(ledger_path, self.project_root),
                "ledger_backup_path": display_path(backup_path, self.project_root),
                **ledger_snapshot,
                "state": "PREPARING",
                "research_verdict": None,
                "created_at": _now(),
                "updated_at": _now(),
                "steps": [],
            }
            _step(journal, "ledger_snapshot_persisted")
            self._write_journal(journal_path, journal)
            try:
                publisher = TransactionalCampaignPublisher(
                    project_root=self.project_root,
                    active_campaign_root=self.layout.active_campaign_root,
                    duplicate_guard=self._duplicate_guard,
                )
                published = publisher.publish(compiled)
                _step(journal, "source_tree_installed")
                self._write_journal(journal_path, journal)
                rows, _ = append_planned_publication(
                    draft,
                    project_root=self.project_root,
                    active_campaign_root=self.layout.active_campaign_root,
                )
                journal["ledger_after_sha256"] = _sha256(ledger_path)
                _step(journal, "planned_ledger_rows_appended", rows=rows)
                self._write_journal(journal_path, journal)
                refresh = refresh_generated_indexes_if_stale(self.project_root, force=True)
                if refresh.get("refreshed") is not True:
                    raise RuntimeError("forced registry and view refresh did not report refreshed=true")
                _step(journal, "registry_and_views_refreshed", refreshed=bool(refresh.get("refreshed")))
                journal["state"] = "COMPLETED"
                journal["research_verdict"] = "PASS"
                journal["updated_at"] = _now()
                self._write_journal(journal_path, journal)
            except Exception as exc:
                journal["error"] = f"{type(exc).__name__}: {exc}"
                rollback_errors = self._rollback_locked(journal_path, journal)
                if rollback_errors:
                    raise RuntimeError(
                        "publication failed and rollback is incomplete; NEEDS MANUAL REVIEW: "
                        + "; ".join(rollback_errors)
                    ) from exc
                raise
        assert published is not None
        return StudioPublishResult(
            campaign_id=published.campaign_id,
            destination=published.destination,
            files=published.files,
            file_sha256=dict(published.file_sha256),
            draft_sha256=published.draft_sha256,
            ledger_rows_appended=rows,
            indexes_refreshed=bool(refresh.get("refreshed")),
            journal_path=journal_path,
        )

    def recover(self) -> list[dict[str, Any]]:
        """Explicitly recover every abandoned PREPARING publication.

        Recovery is serialized with publication across processes.  It never
        restores an old ledger wholesale when later rows have been committed.
        """

        with _publication_file_lock(self.lock_path), _working_directory(self.project_root):
            return self._recover_preparing_locked()

    def _recover_preparing_locked(self) -> list[dict[str, Any]]:
        recovered: list[dict[str, Any]] = []
        if not self.journal_root.is_dir():
            return recovered
        for journal_path in sorted(self.journal_root.glob("*.json")):
            try:
                journal = _read_json_mapping(journal_path)
            except (OSError, ValueError) as exc:
                raise RuntimeError(
                    f"publication journal is unreadable; NEEDS MANUAL REVIEW: {journal_path}: {exc}"
                ) from exc
            if journal.get("schema") != "alphaquest.studio-publication-journal/v1":
                raise RuntimeError(f"publication journal schema is unsupported; NEEDS MANUAL REVIEW: {journal_path}")
            if journal.get("state") != "PREPARING":
                continue
            journal["recovery_reason"] = "abandoned PREPARING transaction recovered before new publication"
            errors = self._rollback_locked(journal_path, journal)
            recovered.append(
                {
                    "journal_path": journal_path,
                    "campaign_id": journal.get("campaign_id"),
                    "state": journal.get("state"),
                    "rollback_errors": list(errors),
                }
            )
            if errors:
                raise RuntimeError("publication recovery is incomplete; NEEDS MANUAL REVIEW: " + "; ".join(errors))
        return recovered

    def _rollback_locked(self, journal_path: Path, journal: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        destination = _journal_path(journal.get("destination"), self.project_root)
        if destination is None:
            errors.append("source rollback failed: journal destination identity is missing")
        elif destination.parent != self.layout.active_campaign_root.resolve():
            errors.append("source rollback failed: journal destination is outside the active campaign root")
        elif destination.exists() or destination.is_symlink():
            try:
                installed_draft = _installed_draft_sha256(destination)
                if installed_draft != str(journal.get("draft_sha256") or ""):
                    raise ValueError(
                        "destination does not match the journal draft identity; refusing destructive rollback"
                    )
                if destination.is_symlink() or destination.is_file():
                    destination.unlink()
                else:
                    shutil.rmtree(destination)
                _step(journal, "source_tree_rolled_back")
            except (OSError, ValueError) as exc:
                errors.append(f"source rollback failed: {exc}")

        try:
            mode = _rollback_ledger_transaction(
                journal,
                self.project_root,
                journal_root=self.journal_root,
            )
            _step(journal, "ledger_rolled_back", mode=mode)
        except (OSError, ValueError) as exc:
            errors.append(f"ledger rollback failed: {exc}")

        try:
            refresh = refresh_generated_indexes_if_stale(self.project_root, force=True)
            if refresh.get("refreshed") is not True:
                raise RuntimeError("forced rollback refresh did not report refreshed=true")
            _step(journal, "registry_and_views_rebuilt_after_rollback", refreshed=True)
        except Exception as exc:  # rebuilding derived state is part of rollback integrity
            errors.append(f"registry/view rollback refresh failed: {type(exc).__name__}: {exc}")

        journal["state"] = "NEEDS MANUAL REVIEW" if errors else "ROLLED_BACK"
        journal["research_verdict"] = "NEEDS MANUAL REVIEW" if errors else None
        journal["rollback_errors"] = errors
        journal["updated_at"] = _now()
        self._write_journal(journal_path, journal)
        return errors

    def preflight_draft(self, draft: CampaignDraftV1 | dict[str, Any]) -> dict[str, Any]:
        """Run every read-only publication check before a draft becomes immutable."""

        parsed = draft if isinstance(draft, CampaignDraftV1) else CampaignDraftV1.model_validate(draft)
        if not parsed.frozen:
            raise ValueError("pre-publication validation requires the exact candidate protocol with frozen=true")
        self._require_governed_dataset_manifest(parsed)
        self._recheck_dataset_hash(parsed)
        compiled = self._compiler().compile(parsed)
        with _working_directory(self.project_root):
            publisher = TransactionalCampaignPublisher(
                project_root=self.project_root,
                active_campaign_root=self.layout.active_campaign_root,
                duplicate_guard=self._duplicate_guard,
            )
            hashes = publisher.validate(compiled)
        return {
            "campaign_id": parsed.campaign_id,
            "draft_sha256": compiled.draft_sha256,
            "variant_count": len(compiled.variant_configs),
            "staged_file_sha256": hashes,
            "preflight_verdict": "PASS",
        }

    def _compiler(self) -> CampaignCompiler:
        return CampaignCompiler(
            evidence_root=display_path(self.layout.evidence_roots[0], self.project_root),
            research_artifact_root=display_path(
                self.layout.research_artifact_root,
                self.project_root,
            ),
        )

    def _duplicate_guard(self, draft: CampaignDraftV1) -> None:
        matches = duplicate_matches(
            project_root=self.project_root,
            campaign_id=draft.campaign_id,
            title=draft.title,
            hypothesis=draft.hypothesis,
            expected_mechanism=draft.expected_mechanism,
            fingerprint=draft.economic_edge_fingerprint.model_dump(mode="json"),
        )
        reviewed = set(draft.duplicate_review.reviewed_campaign_ids)
        missing_reviews = sorted(item["campaign_id"] for item in matches if item["campaign_id"] not in reviewed)
        if missing_reviews:
            raise ValueError("unreviewed deterministic duplicate matches: " + ", ".join(missing_reviews))
        if matches and len(draft.duplicate_review.substantive_distinction.strip()) < 80:
            raise ValueError("duplicate distinction must contain at least 80 characters when prior work matches")

    def _recheck_dataset_hash(self, draft: CampaignDraftV1) -> None:
        path = Path(draft.dataset.path)
        canonical = path if path.is_absolute() else self.project_root / path
        if not canonical.is_file():
            raise FileNotFoundError(f"governed canonical dataset is missing: {canonical}")
        actual = _sha256(canonical)
        if actual != draft.dataset.canonical_sha256:
            raise ValueError(
                "canonical dataset hash changed after review; re-import and reconfirm the research protocol"
            )
        if draft.dataset.source_sha256 != actual:
            attachments = self.layout.studio_runtime_root / "raw-attachments" / draft.dataset.dataset_id
            source_verified = (
                any(
                    path.is_file() and _sha256(path) == draft.dataset.source_sha256 for path in attachments.glob("**/*")
                )
                if attachments.is_dir()
                else False
            )
            if not source_verified:
                raise ValueError(
                    "quarantined source attachment is missing or its hash changed after review; re-import the dataset"
                )

    def _require_governed_dataset_manifest(self, draft: CampaignDraftV1) -> DatasetManifestV1:
        manifest_path = self.layout.dataset_root / draft.dataset.dataset_id / "dataset_manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(
                f"governed dataset manifest is missing for {draft.dataset.dataset_id}: {manifest_path}"
            )
        try:
            document = json.loads(manifest_path.read_text(encoding="utf-8"))
            governed = DatasetManifestV1.model_validate(document)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"governed dataset manifest is invalid: {manifest_path}: {exc}") from exc
        if governed.model_dump(mode="json", by_alias=True) != draft.dataset.model_dump(mode="json", by_alias=True):
            raise ValueError(
                "draft dataset metadata differs from the governed dataset manifest; reselect and reconfirm the dataset"
            )
        canonical = Path(governed.path)
        canonical = canonical.resolve() if canonical.is_absolute() else (self.project_root / canonical).resolve()
        try:
            canonical.relative_to(self.layout.dataset_root.resolve())
        except ValueError as exc:
            raise ValueError("governed canonical dataset path must remain inside the configured dataset root") from exc
        if governed.roll_calendar:
            roll_path = Path(governed.roll_calendar)
            roll_calendar = roll_path if roll_path.is_absolute() else self.project_root / roll_path
            if not roll_calendar.is_file():
                raise FileNotFoundError(f"governed roll calendar is missing: {roll_calendar}")
            if _sha256(roll_calendar) != governed.roll_calendar_sha256:
                raise ValueError(
                    "roll calendar hash changed after review; re-import and reconfirm the research protocol"
                )
        return governed

    def _write_journal(self, path: Path, payload: dict[str, Any]) -> None:
        _atomic_write_bytes(
            path,
            (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _step(journal: dict[str, Any], name: str, **details: Any) -> None:
    journal["steps"].append({"name": name, "completed_at": _now(), **details})
    journal["updated_at"] = _now()


def _persist_ledger_backup(ledger_path: Path, backup_path: Path) -> dict[str, Any]:
    existed = ledger_path.is_file()
    payload = ledger_path.read_bytes() if existed else b""
    _atomic_write_bytes(backup_path, payload)
    return {
        "ledger_existed_before": existed,
        "ledger_before_sha256": _sha256_bytes(payload),
        "ledger_backup_sha256": _sha256_bytes(payload),
    }


def _rollback_ledger_transaction(
    journal: dict[str, Any],
    project_root: Path,
    *,
    journal_root: Path,
) -> str:
    ledger_path = _journal_path(journal.get("ledger_path"), project_root)
    expected_ledger = (project_root / "research_ledger.csv").resolve()
    if ledger_path != expected_ledger:
        raise ValueError("journal ledger identity does not match research_ledger.csv")
    backup_path = _journal_path(journal.get("ledger_backup_path"), project_root)
    if backup_path is None or backup_path.parent != journal_root.resolve():
        raise ValueError("journal ledger backup identity is missing or outside the publication journal root")
    if not backup_path.is_file():
        raise ValueError(f"persisted ledger backup is missing: {backup_path}")
    backup = backup_path.read_bytes()
    expected_backup_hash = str(journal.get("ledger_backup_sha256") or "")
    if _sha256_bytes(backup) != expected_backup_hash:
        raise ValueError("persisted ledger backup hash does not match the journal")
    before_hash = str(journal.get("ledger_before_sha256") or "")
    if before_hash != _sha256_bytes(backup):
        raise ValueError("ledger before-hash does not match the persisted backup")

    current = ledger_path.read_bytes() if ledger_path.is_file() else b""
    current_hash = _sha256_bytes(current)
    if current_hash == before_hash:
        return "already_at_snapshot"
    after_hash = str(journal.get("ledger_after_sha256") or "")
    if after_hash and current_hash == after_hash:
        _restore_ledger_snapshot(
            ledger_path,
            backup,
            existed=journal.get("ledger_existed_before") is True,
        )
        return "exact_snapshot_restore"

    backup_rows = _ledger_rows(backup, allow_missing=journal.get("ledger_existed_before") is not True)
    current_rows = _ledger_rows(current, allow_missing=not current)
    backup_fingerprints = {_ledger_fingerprint(row) for row in backup_rows}
    retained: list[dict[str, str]] = []
    removed = 0
    for row in current_rows:
        if _publication_ledger_row(row, journal) and _ledger_fingerprint(row) not in backup_fingerprints:
            removed += 1
            continue
        retained.append(row)
    if removed:
        if not retained and journal.get("ledger_existed_before") is not True:
            ledger_path.unlink(missing_ok=True)
        else:
            _write_ledger_rows(ledger_path, retained)
        return "transaction_rows_removed_preserving_concurrent_rows"
    return "no_transaction_rows_present_preserving_concurrent_rows"


def _restore_ledger_snapshot(path: Path, payload: bytes, *, existed: bool) -> None:
    if not existed:
        path.unlink(missing_ok=True)
        return
    _atomic_write_bytes(path, payload)


def _ledger_rows(payload: bytes, *, allow_missing: bool) -> list[dict[str, str]]:
    if not payload:
        if allow_missing:
            return []
        raise ValueError("persisted ledger snapshot is empty")
    with io.StringIO(payload.decode("utf-8"), newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != LEDGER_FIELDS:
            raise ValueError("research ledger header does not match the governed append contract")
        return list(reader)


def _write_ledger_rows(path: Path, rows: list[dict[str, str]]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=LEDGER_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    _atomic_write_bytes(path, buffer.getvalue().encode("utf-8"))


def _ledger_fingerprint(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(str(row.get(field) or "") for field in LEDGER_FIELDS)


def _publication_ledger_row(row: dict[str, str], journal: dict[str, Any]) -> bool:
    if (
        row.get("campaign_id") != str(journal.get("campaign_id") or "")
        or row.get("stage") != "stage_1"
        or row.get("result") != "planned"
    ):
        return False
    destination = str(journal.get("destination") or "").rstrip("/")
    config_path = str(row.get("config_path") or "")
    return config_path == f"{destination}/campaign.yaml" or config_path.startswith(f"{destination}/variants/")


def _installed_draft_sha256(destination: Path) -> str:
    manifest = _read_json_mapping(destination / "authoring_manifest.json")
    value = str(manifest.get("draft_sha256") or "")
    if len(value) != 64:
        raise ValueError("installed source tree lacks a valid authoring-manifest draft identity")
    return value


def _journal_path(value: Any, project_root: Path) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return (path if path.is_absolute() else project_root / path).resolve()


def _read_json_mapping(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read JSON mapping {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must be a mapping: {path}")
    return value


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _publication_file_lock(path: Path):
    """Serialize Studio publication and recovery across local processes."""

    with _PUBLICATION_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def _working_directory(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


__all__ = ["StudioPublicationService", "StudioPublishResult"]
