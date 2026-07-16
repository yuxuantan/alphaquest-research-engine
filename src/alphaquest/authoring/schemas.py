from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from alphaquest.authoring.models import (
    BarRuleV1,
    CampaignDraftV1,
    DatasetManifestV1,
    ModuleManifestV1,
    VariantDraftV1,
)


_SCHEMA_MODELS = {
    "campaign-draft-v1.schema.json": CampaignDraftV1,
    "variant-draft-v1.schema.json": VariantDraftV1,
    "module-manifest-v1.schema.json": ModuleManifestV1,
    "dataset-manifest-v1.schema.json": DatasetManifestV1,
    "bar-rule-v1.schema.json": BarRuleV1,
}


def authoring_schema_documents() -> dict[str, dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    for filename, model in _SCHEMA_MODELS.items():
        document = deepcopy(model.model_json_schema(by_alias=True, mode="validation"))
        document["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        document["$id"] = f"https://alphaquest.local/schemas/{filename}"
        documents[filename] = document
    return documents


def write_authoring_schemas(
    output_root: str | Path = "schemas",
    *,
    check: bool = False,
) -> tuple[Path, ...]:
    root = Path(output_root)
    changed: list[Path] = []
    for filename, document in authoring_schema_documents().items():
        path = root / filename
        expected = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        actual = path.read_text(encoding="utf-8") if path.is_file() else None
        if actual == expected:
            continue
        changed.append(path)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8")
    if check and changed:
        names = ", ".join(str(path) for path in changed)
        raise RuntimeError(f"authoring JSON schemas are stale or missing: {names}")
    return tuple(changed)


__all__ = ["authoring_schema_documents", "write_authoring_schemas"]
