"""Draft persistence and validation for Research Studio.

Drafts deliberately live outside campaign discovery.  This module accepts
incomplete mappings so a presentation layer can save every wizard step, while the
strict authoring model remains the only path to compilation and publication.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from pydantic import ValidationError

from alphaquest.authoring.models import CampaignDraftV1
from alphaquest.research.storage import load_storage_layout


_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_]*$")
CLOSED_BEFORE_PNL_SCHEMA = "alphaquest.studio-draft-closure/v1"


class DraftStore:
    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        layout = load_storage_layout(self.project_root)
        self.root = Path(getattr(layout, "draft_root", self.project_root / "research" / "drafts"))

    def list(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self.root.is_dir():
            return rows
        ledger_closed = _ledger_duplicate_closures(self.project_root)
        layout = load_storage_layout(self.project_root)
        published_ids = {
            path.parent.name
            for campaign_root in layout.campaign_roots
            if campaign_root.is_dir()
            for path in campaign_root.glob("*/campaign.yaml")
        }
        for path in sorted(self.root.glob("*/draft.json")):
            document = _read_json(path)
            if not document:
                continue
            payload = document.get("draft") if isinstance(document.get("draft"), dict) else document
            campaign_id = str(payload.get("campaign_id") or path.parent.name)
            if (
                _has_closed_before_pnl_marker(document)
                or campaign_id in ledger_closed
                or campaign_id in published_ids
            ):
                continue
            rows.append(
                {
                    "campaign_id": campaign_id,
                    "title": payload.get("title") or "Untitled research idea",
                    "instrument": payload.get("instrument"),
                    "wizard_step": int(document.get("wizard_step") or 1),
                    "frozen": bool(payload.get("frozen")),
                    "updated_at": document.get("updated_at"),
                    "path": str(path),
                }
            )
        return sorted(rows, key=lambda row: str(row.get("updated_at") or ""), reverse=True)

    def load(self, campaign_id: str) -> dict[str, Any]:
        document = _read_json(self.path_for(campaign_id))
        if not document:
            raise FileNotFoundError(f"Studio draft not found: {campaign_id}")
        return document

    def save(self, campaign_id: str, draft: dict[str, Any], *, wizard_step: int) -> Path:
        path = self.path_for(campaign_id)
        if draft.get("campaign_id") not in (None, campaign_id):
            raise ValueError("draft campaign_id does not match its storage key")
        normalized_draft = {**draft, "campaign_id": campaign_id}
        existing = _read_json(path)
        if _has_closed_before_pnl_marker(existing) or campaign_id in _ledger_duplicate_closures(self.project_root):
            raise ValueError(
                "the research draft was closed before PnL as a duplicate FAIL and is immutable"
            )
        existing_draft = existing.get("draft") if isinstance(existing.get("draft"), dict) else {}
        if existing_draft.get("frozen"):
            _verify_frozen_document(existing, campaign_id)
            if _canonical_json(existing_draft) != _canonical_json(normalized_draft):
                raise ValueError(
                    "frozen Studio drafts are immutable; create an explicit governed follow-up attempt instead"
                )
        payload = {
            "schema": "alphaquest.studio-autosave/v1",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "wizard_step": max(1, min(7, int(wizard_step))),
            "draft": normalized_draft,
        }
        if normalized_draft.get("frozen"):
            payload["frozen_draft_sha256"] = _sha256_json(normalized_draft)
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_json(path, payload)
        return path

    def load_state(self, campaign_id: str) -> dict[str, Any]:
        return _read_json(self.path_for(campaign_id).with_name("wizard_state.json"))

    def save_state(self, campaign_id: str, state: dict[str, Any]) -> Path:
        document = _read_json(self.path_for(campaign_id))
        if self.is_closed_before_pnl(campaign_id, document=document):
            raise ValueError(
                "the research draft was closed before PnL as a duplicate FAIL and is immutable"
            )
        draft = document.get("draft") if isinstance(document.get("draft"), dict) else {}
        if draft.get("frozen"):
            raise ValueError("wizard state is immutable after the research protocol is frozen")
        path = self.path_for(campaign_id).with_name("wizard_state.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_json(path, state)
        return path

    def validate(self, campaign_id: str) -> CampaignDraftV1:
        document = self.load(campaign_id)
        if self.is_closed_before_pnl(campaign_id, document=document):
            raise ValueError("a duplicate FAIL closed before PnL cannot be frozen or published")
        payload = document.get("draft") if isinstance(document.get("draft"), dict) else document
        if payload.get("frozen"):
            _verify_frozen_document(document, campaign_id)
        return CampaignDraftV1.model_validate(payload)

    def replace_frozen_sequence(self, campaign_id: str, draft: CampaignDraftV1) -> Path:
        """Atomically advance a published frozen draft by one governed variant."""

        if draft.campaign_id != campaign_id or not draft.frozen:
            raise ValueError("sequential replacement requires the same frozen campaign identity")
        path = self.path_for(campaign_id)
        existing = self.load(campaign_id)
        _verify_frozen_document(existing, campaign_id)
        previous = existing.get("draft") if isinstance(existing.get("draft"), dict) else {}
        old_ids = [str(item.get("variant_id") or "") for item in previous.get("variants") or []]
        new_payload = draft.model_dump(mode="json", by_alias=True)
        new_ids = [str(item.get("variant_id") or "") for item in new_payload.get("variants") or []]
        if new_ids[:-1] != old_ids or len(new_ids) != len(old_ids) + 1:
            raise ValueError("a sequential replacement may append exactly one variant and may not edit prior variants")
        payload = {
            **existing,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "wizard_step": 7,
            "draft": new_payload,
            "frozen_draft_sha256": _sha256_json(new_payload),
        }
        _atomic_json(path, payload)
        return path

    def validation_report(self, campaign_id: str) -> dict[str, Any]:
        try:
            draft = self.validate(campaign_id)
        except (FileNotFoundError, ValidationError, ValueError) as exc:
            errors = exc.errors() if isinstance(exc, ValidationError) else [{"loc": (), "msg": str(exc)}]
            return {
                "valid": False,
                "campaign_id": campaign_id,
                "errors": [
                    {"field": ".".join(str(part) for part in item.get("loc", ())), "message": item.get("msg")}
                    for item in errors
                ],
            }
        return {
            "valid": True,
            "campaign_id": draft.campaign_id,
            "frozen": draft.frozen,
            "variant_count": len(draft.variants),
            "confirmed_variants": sum(variant.confirmed for variant in draft.variants),
            "dataset_verdict": draft.dataset.quality_verdict,
            "duplicate_conclusion": draft.duplicate_review.conclusion,
            "errors": [],
        }

    def close_before_pnl(
        self,
        campaign_id: str,
        *,
        ledger_path: str | Path,
        reason: str,
    ) -> dict[str, Any]:
        """Atomically install the terminal duplicate-closure marker."""

        path = self.path_for(campaign_id)
        document = self.load(campaign_id)
        existing = document.get("closed_before_pnl")
        if isinstance(existing, dict) and existing.get("status") == "CLOSED":
            return dict(existing)
        payload = document.get("draft") if isinstance(document.get("draft"), dict) else document
        if payload.get("frozen"):
            raise ValueError("a frozen research protocol cannot be closed through duplicate review")
        reason_value = reason.strip()
        if len(reason_value) < 80:
            raise ValueError("duplicate closure requires a substantive reason of at least 80 characters")
        marker = {
            "schema": CLOSED_BEFORE_PNL_SCHEMA,
            "status": "CLOSED",
            "research_verdict": "FAIL",
            "stage": "duplicate_review",
            "closed_at": datetime.now(timezone.utc).isoformat(),
            "ledger_path": str(Path(ledger_path)),
            "reason": reason_value,
            "draft_sha256": _sha256_json(payload),
        }
        _atomic_json(path, {**document, "closed_before_pnl": marker})
        return marker

    def is_closed_before_pnl(
        self,
        campaign_id: str,
        *,
        document: dict[str, Any] | None = None,
    ) -> bool:
        value = document if document is not None else _read_json(self.path_for(campaign_id))
        return _has_closed_before_pnl_marker(value) or campaign_id in _ledger_duplicate_closures(
            self.project_root
        )

    def create_revision(
        self,
        campaign_id: str,
        revision_campaign_id: str,
        *,
        reason: str,
    ) -> Path:
        """Clone a blocked frozen protocol into a new editable, pre-PnL draft."""

        reason_value = reason.strip()
        if len(reason_value) < 20:
            raise ValueError("revision reason must explain the publication blocker")
        original = self.load(campaign_id)
        if self.is_closed_before_pnl(campaign_id, document=original):
            raise ValueError("a duplicate FAIL closed before PnL cannot be revised or reopened")
        _verify_frozen_document(original, campaign_id)
        payload = original.get("draft") if isinstance(original.get("draft"), dict) else {}
        if not payload.get("frozen"):
            raise ValueError("only an immutable frozen protocol can be revised through this workflow")
        destination = self.path_for(revision_campaign_id)
        if destination.exists():
            raise FileExistsError(f"Studio draft already exists: {revision_campaign_id}")
        revised = json.loads(_canonical_json(payload))
        revised["campaign_id"] = revision_campaign_id
        revised["title"] = f"{payload.get('title') or campaign_id} — revised"
        revised["frozen"] = False
        revised.pop("confirmation_context_sha256", None)
        revised.pop("duplicate_review", None)
        for variant in revised.get("variants") or []:
            if isinstance(variant, dict):
                variant["confirmed"] = False
        path = self.save(revision_campaign_id, revised, wizard_step=2)
        self.save_state(
            revision_campaign_id,
            {
                "revision_of": campaign_id,
                "frozen_parent_sha256": str(original.get("frozen_draft_sha256") or ""),
                "reason": reason_value,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return path

    def path_for(self, campaign_id: str) -> Path:
        if _IDENTIFIER.fullmatch(campaign_id) is None:
            raise ValueError("campaign ID must use lowercase letters, numbers, and underscores")
        return self.root / campaign_id / "draft.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _verify_frozen_document(document: dict[str, Any], campaign_id: str) -> None:
    payload = document.get("draft") if isinstance(document.get("draft"), dict) else document
    expected = str(document.get("frozen_draft_sha256") or "")
    actual = _sha256_json(payload)
    if not expected or expected != actual:
        raise ValueError(
            f"frozen draft integrity check failed for {campaign_id}; publication is blocked pending manual review"
        )


def _has_closed_before_pnl_marker(document: dict[str, Any]) -> bool:
    marker = document.get("closed_before_pnl")
    if not isinstance(marker, dict):
        return bool(marker)
    # A malformed or partial marker fails closed rather than reopening work.
    return bool(marker)


def _ledger_duplicate_closures(project_root: Path) -> set[str]:
    path = project_root / "research_ledger.csv"
    if not path.is_file():
        return set()
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return {
                str(row.get("campaign_id") or "").strip()
                for row in reader
                if str(row.get("stage") or "").strip() == "duplicate_review"
                and str(row.get("result") or "").strip().upper() == "FAIL"
                and str(row.get("campaign_id") or "").strip()
            }
    except (OSError, UnicodeError, csv.Error):
        # Marker checks remain available; governed mutations that depend on the
        # ledger will fail separately in the ledger service.
        return set()


__all__ = ["CLOSED_BEFORE_PNL_SCHEMA", "DraftStore"]
