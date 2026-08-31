"""Immutable local cache for deterministic canonical-event replay results."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import shutil
import tempfile
from typing import Any

import pandas as pd

from alphaquest.research.storage import load_storage_layout
from alphaquest.utils.hashing import file_sha256, object_sha256


CACHE_SCHEMA = "alphaquest.event-replay-result-cache/v2"
FRAME_NAMES = ("trades", "daily", "session_audits", "event_transitions")


def event_replay_cache_key(config: dict[str, Any], input_hash: str) -> str:
    return object_sha256(
        {
            "schema": CACHE_SCHEMA,
            "execution_config": _execution_config(config),
            "input_data_hash": str(input_hash),
        }
    )


def _execution_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return only values that can change canonical replay outputs.

    Attempt IDs, evidence destinations, reviewer metadata, and worker counts
    must not invalidate reusable deterministic replay results.  Strategy,
    execution-data, fill, session, and certification identities remain bound.
    """

    keys = (
        "symbol",
        "timeframe",
        "timezone",
        "engine_lane",
        "data",
        "strategy",
        "strategy_certification",
        "core",
        "execution",
        "prop_rules",
    )
    value = {
        key: deepcopy(config[key])
        for key in keys
        if key in config
    }
    core = value.get("core")
    if isinstance(core, dict):
        core.pop("event_replay_result_cache", None)
        core.pop("event_replay_session_workers", None)
        core.pop("event_replay_idle_batch", None)
        core.pop("event_replay_strategy_hints", None)
    return value


def load_event_replay_cache(
    config: dict[str, Any],
    input_hash: str,
    *,
    project_root: str | Path = ".",
) -> dict[str, Any] | None:
    key = event_replay_cache_key(config, input_hash)
    root = _cache_root(project_root) / key
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if manifest.get("schema") != CACHE_SCHEMA or manifest.get("cache_key") != key:
        return None
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    for name, expected in artifacts.items():
        path = root / name
        if not path.is_file() or file_sha256(path) != str(expected):
            return None
    try:
        result = {
            name: pd.read_parquet(root / f"{name}.parquet")
            for name in FRAME_NAMES
        }
        mappings = json.loads((root / "mappings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    result.update(
        {
            "metrics": dict(mappings.get("metrics") or {}),
            "diagnostics": dict(mappings.get("diagnostics") or {}),
            "reproducibility": {
                **dict(mappings.get("reproducibility") or {}),
                "result_cache_hit": True,
                "result_cache_key": key,
            },
        }
    )
    return result


def write_event_replay_cache(
    config: dict[str, Any],
    input_hash: str,
    result: dict[str, Any],
    *,
    project_root: str | Path = ".",
) -> str:
    key = event_replay_cache_key(config, input_hash)
    cache_parent = _cache_root(project_root)
    cache_parent.mkdir(parents=True, exist_ok=True)
    destination = cache_parent / key
    if destination.is_dir():
        return key
    temporary = Path(tempfile.mkdtemp(prefix=f".{key[:12]}-", dir=cache_parent))
    try:
        for name in FRAME_NAMES:
            frame = result.get(name)
            if not isinstance(frame, pd.DataFrame):
                raise TypeError(f"event replay cache field {name!r} must be a DataFrame")
            frame.to_parquet(temporary / f"{name}.parquet", index=False)
        mappings = {
            "metrics": result.get("metrics") or {},
            "diagnostics": result.get("diagnostics") or {},
            "reproducibility": {
                **dict(result.get("reproducibility") or {}),
                "result_cache_hit": False,
                "result_cache_key": key,
            },
        }
        (temporary / "mappings.json").write_text(
            json.dumps(mappings, sort_keys=True, default=str),
            encoding="utf-8",
        )
        artifacts = {
            path.name: file_sha256(path)
            for path in sorted(temporary.iterdir())
            if path.is_file()
        }
        (temporary / "manifest.json").write_text(
            json.dumps(
                {
                    "schema": CACHE_SCHEMA,
                    "cache_key": key,
                    "input_data_hash": str(input_hash),
                    "artifacts": artifacts,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        try:
            temporary.rename(destination)
        except FileExistsError:
            pass
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return key


def _cache_root(project_root: str | Path) -> Path:
    root = Path(project_root).resolve()
    return load_storage_layout(root).run_store_root / "event-replay-cache"


__all__ = [
    "CACHE_SCHEMA",
    "event_replay_cache_key",
    "load_event_replay_cache",
    "write_event_replay_cache",
]
