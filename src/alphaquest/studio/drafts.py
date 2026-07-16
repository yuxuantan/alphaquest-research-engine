"""Draft persistence and validation for Research Studio.

Drafts deliberately live outside campaign discovery.  This module accepts
incomplete mappings so Streamlit can autosave every wizard step, while the
strict authoring model remains the only path to compilation and publication.
"""

from __future__ import annotations

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


class DraftStore:
    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        layout = load_storage_layout(self.project_root)
        self.root = Path(getattr(layout, "draft_root", self.project_root / "research" / "drafts"))

    def list(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self.root.is_dir():
            return rows
        for path in sorted(self.root.glob("*/draft.json")):
            document = _read_json(path)
            if not document:
                continue
            payload = document.get("draft") if isinstance(document.get("draft"), dict) else document
            rows.append(
                {
                    "campaign_id": payload.get("campaign_id") or path.parent.name,
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
        draft = document.get("draft") if isinstance(document.get("draft"), dict) else {}
        if draft.get("frozen"):
            raise ValueError("wizard state is immutable after the research protocol is frozen")
        path = self.path_for(campaign_id).with_name("wizard_state.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_json(path, state)
        return path

    def validate(self, campaign_id: str) -> CampaignDraftV1:
        document = self.load(campaign_id)
        payload = document.get("draft") if isinstance(document.get("draft"), dict) else document
        if payload.get("frozen"):
            _verify_frozen_document(document, campaign_id)
        return CampaignDraftV1.model_validate(payload)

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


__all__ = ["DraftStore"]
