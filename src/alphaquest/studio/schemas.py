"""Generated JSON Schema documents for public Studio operational contracts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from alphaquest.studio.candidate_review import CandidateReviewV1
from alphaquest.studio.jobs import JobRecordV1
from alphaquest.studio.results import ResultBundleV2


STUDIO_SCHEMA_MODELS = {
    "candidate-review-v1.schema.json": CandidateReviewV1,
    "job-record-v1.schema.json": JobRecordV1,
    "result-bundle-v2.schema.json": ResultBundleV2,
}


def studio_schema_documents() -> dict[str, dict[str, Any]]:
    return {
        filename: model.model_json_schema(by_alias=True)
        for filename, model in STUDIO_SCHEMA_MODELS.items()
    }


def write_studio_schema_documents(output_dir: str | Path) -> list[Path]:
    """Atomically refresh committed schemas from their owning Pydantic models."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for filename, document in studio_schema_documents().items():
        path = directory / filename
        data = (json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        with NamedTemporaryFile(dir=directory, prefix=f".{filename}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        written.append(path)
    return written


def stale_studio_schema_documents(output_dir: str | Path) -> list[str]:
    """Return committed schema names that are missing or out of sync."""

    directory = Path(output_dir)
    stale = []
    for filename, expected in studio_schema_documents().items():
        path = directory / filename
        try:
            actual = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stale.append(filename)
            continue
        if actual != expected:
            stale.append(filename)
    return stale
