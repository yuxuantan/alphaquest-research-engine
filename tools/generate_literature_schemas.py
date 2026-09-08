#!/usr/bin/env python3
"""Generate the 13 checked-in P3 JSON Schema contracts from Pydantic models."""

from __future__ import annotations

import json
from pathlib import Path

from alphaquest.research.literature.contracts import CANONICAL_RECORD_TYPES


ROOT = Path(__file__).resolve().parents[1]
FILENAMES = {
    "protocols": "literature-research-protocol-revision-v1.schema.json",
    "searches": "literature-search-run-revision-v1.schema.json",
    "source-works": "literature-source-identity-revision-v1.schema.json",
    "source-versions": "literature-source-version-identity-revision-v1.schema.json",
    "source-relationships": "literature-source-relationship-revision-v1.schema.json",
    "captures": "literature-source-capture-revision-v1.schema.json",
    "claims": "literature-claim-extraction-revision-v1.schema.json",
    "evidence-relations": "literature-evidence-relation-revision-v1.schema.json",
    "dossiers": "literature-edge-dossier-revision-v1.schema.json",
    "dossier-freezes": "literature-dossier-freeze-v1.schema.json",
    "codex-attempts": "literature-codex-task-attempt-revision-v1.schema.json",
    "p2-emissions": "literature-p2-emission-operation-revision-v1.schema.json",
    "p2-emission-receipts": "literature-p2-emission-receipt-v1.schema.json",
}


def main() -> None:
    for model in CANONICAL_RECORD_TYPES:
        model.model_rebuild()
        schema = model.model_json_schema(by_alias=True, mode="validation")
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"https://alphaquest.local/schemas/{FILENAMES[model.family]}"
        schema.setdefault("properties", {}).setdefault("schema", {})["const"] = model.schema_literal
        required = schema.setdefault("required", [])
        if "schema" not in required:
            required.insert(0, "schema")
        destination = ROOT / "schemas" / FILENAMES[model.family]
        destination.write_text(
            json.dumps(schema, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
