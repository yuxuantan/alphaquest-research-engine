"""Fail-closed catalog for generic execution simulation capabilities."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml


def list_execution_profiles(project_root: str | Path = ".") -> list[dict[str, Any]]:
    root = Path(project_root).resolve()
    manifest_root = root / "src" / "alphaquest" / "execution_certifications"
    rows: list[dict[str, Any]] = []
    for path in sorted(manifest_root.glob("*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            rows.append(
                {
                    "profile_id": path.stem,
                    "status": "unavailable",
                    "reason": f"manifest cannot be read: {exc}",
                }
            )
            continue
        source_hashes: dict[str, str] = {}
        errors: list[str] = []
        for relative in payload.get("source_files") or []:
            source = (root / str(relative)).resolve()
            if not source.is_relative_to(root) or not source.is_file():
                errors.append(f"execution source is missing: {relative}")
                continue
            source_hashes[str(relative)] = hashlib.sha256(source.read_bytes()).hexdigest()
        combined = hashlib.sha256(
            "".join(f"{name}:{digest}\n" for name, digest in sorted(source_hashes.items())).encode()
        ).hexdigest()
        if combined != str(payload.get("implementation_sha256") or ""):
            errors.append("execution implementation hash is stale")
        required = {
            "market",
            "limit",
            "stop",
            "stop_limit",
            "oco",
            "partial_fills",
            "bid_ask_replay",
            "no_lookahead",
        }
        tested = set(payload.get("required_test_categories") or [])
        missing = sorted(required - tested)
        if missing:
            errors.append("required test categories are missing: " + ", ".join(missing))
        rows.append(
            {
                **payload,
                "manifest_path": str(path.relative_to(root)),
                "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "observed_implementation_sha256": combined,
                "status": "certified" if not errors and payload.get("status") == "certified" else "unavailable",
                "errors": errors,
            }
        )
    return rows


__all__ = ["list_execution_profiles"]
