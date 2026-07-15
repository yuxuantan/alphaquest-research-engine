from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


ARTIFACT_CATEGORIES = {
    "catalogs",
    "audits/repository",
    "audits/methodology",
    "audits/density",
    "campaigns",
    "qualification",
    "search_gates",
    "cleanup",
    "migrations",
}
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class ArtifactStore:
    def __init__(self, root: str | Path = "research_artifacts") -> None:
        self.root = Path(root)

    def path(self, category: str, filename: str, *, campaign_id: str | None = None) -> Path:
        if category not in ARTIFACT_CATEGORIES:
            raise ValueError(f"unsupported artifact category: {category}")
        if not _SAFE_NAME.fullmatch(filename):
            raise ValueError(f"unsafe artifact filename: {filename!r}")
        path = self.root / category
        if category == "campaigns":
            if not campaign_id or not _SAFE_NAME.fullmatch(campaign_id):
                raise ValueError("campaign artifacts require a safe campaign_id")
            path /= campaign_id
        return path / filename

    def write_text(
        self,
        category: str,
        filename: str,
        content: str,
        *,
        campaign_id: str | None = None,
    ) -> Path:
        path = self.path(category, filename, campaign_id=campaign_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_json(
        self,
        category: str,
        filename: str,
        payload: Any,
        *,
        campaign_id: str | None = None,
    ) -> Path:
        return self.write_text(
            category,
            filename,
            json.dumps(payload, indent=2, default=str, allow_nan=False) + "\n",
            campaign_id=campaign_id,
        )
