from __future__ import annotations

from copy import deepcopy
import heapq
import json
import math
from pathlib import Path
from typing import Any


ROADMAP_SCHEMA = "alphaquest.development-roadmap/v1"
DEFAULT_ROADMAP_PATH = Path("config/development_roadmap.json")
DECLARED_STATES = frozenset(
    {
        "PLANNED",
        "IMPLEMENTED",
        "VERIFIED",
        "DEFERRED",
        "SKIPPED_SAFEGUARD",
    }
)
ELIGIBLE_STATES = frozenset({"PLANNED", "IMPLEMENTED", "VERIFIED"})
DERIVED_SKIPPED_STATE = "SKIPPED_DEPENDENCY"

# Schema-v1 resource bounds. Dependency depth counts units, so a root has depth one.
MAX_UNITS = 256
MAX_DEPENDENCY_DEPTH = 64
MAX_SKIP_CHAINS_PER_UNIT = 4096


def load_development_status(
    project_root: str | Path,
    roadmap: str | Path | None = None,
) -> dict[str, Any]:
    """Load, validate, and resolve the read-only development dependency report."""

    root = Path(project_root).resolve()
    roadmap_path = _roadmap_path(root, roadmap)
    try:
        raw = roadmap_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read development roadmap {roadmap_path}: {exc}") from exc
    try:
        payload = json.loads(
            raw,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_non_json_constant,
        )
        _validate_finite_numbers(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"invalid development roadmap JSON at {roadmap_path}: {exc}") from exc

    units = _validate_roadmap(payload)
    by_id = {unit["id"]: unit for unit in units}
    _validate_dependencies(by_id)
    topological_order = _topological_order(by_id)
    skip_chains = _build_skip_chains(by_id, topological_order)

    resolved_units = [_resolved_unit(unit, by_id, skip_chains[unit["id"]]) for unit in units]
    counts: dict[str, int] = {}
    for unit in resolved_units:
        state = unit["effective_status"]
        counts[state] = counts.get(state, 0) + 1

    top_level_metadata = {
        key: deepcopy(value)
        for key, value in payload.items()
        if key not in {"schema", "owner_instruction", "scope", "units"}
    }
    return {
        "schema": payload["schema"],
        "owner_instruction": deepcopy(payload["owner_instruction"]),
        "scope": deepcopy(payload["scope"]),
        "metadata": top_level_metadata,
        "roadmap_path": str(roadmap_path),
        "scope_eligibility_only": True,
        "readiness_or_approval_claimed": False,
        "counts_by_effective_status": counts,
        "units": resolved_units,
    }


def select_development_unit(report: dict[str, Any], unit_id: str) -> dict[str, Any] | None:
    for unit in report["units"]:
        if unit["id"] == unit_id:
            selected = deepcopy(unit)
            selected["scope_eligible"] = unit["effective_status"] in ELIGIBLE_STATES
            selected["eligibility_basis"] = "scope_only"
            return selected
    return None


def _roadmap_path(project_root: Path, roadmap: str | Path | None) -> Path:
    candidate = DEFAULT_ROADMAP_PATH if roadmap is None else Path(roadmap)
    return candidate.resolve() if candidate.is_absolute() else (project_root / candidate).resolve()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate object key {key!r}")
        result[key] = value
    return result


def _reject_non_json_constant(value: str) -> None:
    raise ValueError(f"non-JSON numeric constant {value!r}")


def _validate_finite_numbers(payload: Any) -> None:
    pending: list[tuple[str, Any]] = [("$", payload)]
    while pending:
        path, value = pending.pop()
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"non-finite JSON number at {path}")
        if isinstance(value, dict):
            pending.extend((f"{path}.{key}", child) for key, child in value.items())
        elif isinstance(value, list):
            pending.extend((f"{path}[{index}]", child) for index, child in enumerate(value))


def _validate_roadmap(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("development roadmap must be a JSON object")
    if payload.get("schema") != ROADMAP_SCHEMA:
        raise ValueError(f"development roadmap schema must be {ROADMAP_SCHEMA!r}")
    _require_nonempty_object(payload, "owner_instruction", "development roadmap")
    _require_nonempty_object(payload, "scope", "development roadmap")
    _validate_descriptive_object(payload["owner_instruction"], "development roadmap owner_instruction")
    _validate_descriptive_object(payload["scope"], "development roadmap scope")

    units = payload.get("units")
    if not isinstance(units, list):
        raise ValueError("development roadmap units must be an array")
    if len(units) > MAX_UNITS:
        raise ValueError(f"development roadmap units must contain at most {MAX_UNITS} entries")

    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    for index, value in enumerate(units):
        label = f"development roadmap unit at index {index}"
        if not isinstance(value, dict):
            raise ValueError(f"{label} must be an object")
        unit_id = _require_nonblank_string(value, "id", label)
        if unit_id in seen:
            raise ValueError(f"duplicate development unit ID {unit_id!r}")
        seen.add(unit_id)
        _require_nonblank_string(value, "title", f"development unit {unit_id!r}")

        state = value.get("declared_status")
        if not isinstance(state, str) or state not in DECLARED_STATES:
            raise ValueError(
                f"development unit {unit_id!r} declared_status must be one of " f"{sorted(DECLARED_STATES)}"
            )
        dependencies = _require_string_array(
            value,
            "depends_on",
            f"development unit {unit_id!r}",
            allow_empty=True,
        )
        if len(set(dependencies)) != len(dependencies):
            raise ValueError(f"development unit {unit_id!r} contains duplicate dependency IDs")
        _require_string_array(
            value,
            "repercussions",
            f"development unit {unit_id!r}",
            allow_empty=False,
        )

        has_trigger = "trigger" in value
        trigger = value.get("trigger")
        if has_trigger:
            if not isinstance(trigger, dict):
                raise ValueError(f"development unit {unit_id!r} trigger must be an object")
            _require_nonblank_string(trigger, "reason", f"development unit {unit_id!r} trigger")
            _require_nonblank_string(trigger, "evidence_ref", f"development unit {unit_id!r} trigger")
        if state == "SKIPPED_SAFEGUARD" and not has_trigger:
            raise ValueError(f"development unit {unit_id!r} requires a trigger when directly safeguard-skipped")
        if state != "SKIPPED_SAFEGUARD" and has_trigger:
            raise ValueError(f"development unit {unit_id!r} trigger is allowed only for SKIPPED_SAFEGUARD")

        for descriptive_key in ("scope", "dependency_note"):
            if descriptive_key in value:
                _require_nonblank_string(
                    value,
                    descriptive_key,
                    f"development unit {unit_id!r}",
                )

        validated.append(value)
    return validated


def _require_nonblank_string(mapping: dict[str, Any], key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} {key} must be a nonblank string")
    return value


def _require_nonempty_object(mapping: dict[str, Any], key: str, label: str) -> dict[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, dict) or not value:
        raise ValueError(f"{label} {key} must be a nonempty object")
    return value


def _validate_descriptive_object(value: dict[str, Any], label: str) -> None:
    pending: list[tuple[str, Any]] = [(label, value)]
    while pending:
        path, current = pending.pop()
        if isinstance(current, str):
            if not current.strip():
                raise ValueError(f"{path} must not contain blank strings")
        elif isinstance(current, dict):
            for key, child in current.items():
                if not isinstance(key, str) or not key.strip():
                    raise ValueError(f"{path} object keys must be nonblank strings")
                pending.append((f"{path}.{key}", child))
        elif isinstance(current, list):
            for index, child in enumerate(current):
                pending.append((f"{path}[{index}]", child))


def _require_string_array(
    mapping: dict[str, Any],
    key: str,
    label: str,
    *,
    allow_empty: bool,
) -> list[str]:
    value = mapping.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{label} {key} must be an array of nonblank strings")
    if not allow_empty and not value:
        raise ValueError(f"{label} {key} must contain at least one nonblank string")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{label} {key} must be an array of nonblank strings")
    return value


def _validate_dependencies(by_id: dict[str, dict[str, Any]]) -> None:
    for unit_id, unit in by_id.items():
        for dependency_id in unit["depends_on"]:
            if dependency_id not in by_id:
                raise ValueError(f"development unit {unit_id!r} references unknown dependency {dependency_id!r}")


def _topological_order(by_id: dict[str, dict[str, Any]]) -> list[str]:
    unresolved = {unit_id: len(unit["depends_on"]) for unit_id, unit in by_id.items()}
    dependents: dict[str, list[str]] = {unit_id: [] for unit_id in by_id}
    for unit_id, unit in by_id.items():
        for dependency_id in unit["depends_on"]:
            dependents[dependency_id].append(unit_id)

    ready = [unit_id for unit_id, count in unresolved.items() if count == 0]
    heapq.heapify(ready)
    order: list[str] = []
    depths: dict[str, int] = {}
    while ready:
        unit_id = heapq.heappop(ready)
        dependencies = by_id[unit_id]["depends_on"]
        depth = max((depths[dependency_id] + 1 for dependency_id in dependencies), default=1)
        if depth > MAX_DEPENDENCY_DEPTH:
            raise ValueError(
                f"development unit {unit_id!r} exceeds maximum dependency depth " f"{MAX_DEPENDENCY_DEPTH}"
            )
        depths[unit_id] = depth
        order.append(unit_id)
        for dependent_id in sorted(dependents[unit_id]):
            unresolved[dependent_id] -= 1
            if unresolved[dependent_id] == 0:
                heapq.heappush(ready, dependent_id)

    if len(order) != len(by_id):
        unresolved_ids = sorted(unit_id for unit_id, count in unresolved.items() if count)
        raise ValueError("development roadmap dependency cycle involving: " + ", ".join(unresolved_ids))
    return order


def _build_skip_chains(
    by_id: dict[str, dict[str, Any]],
    topological_order: list[str],
) -> dict[str, list[list[str]]]:
    chains_by_id: dict[str, list[list[str]]] = {}
    for unit_id in topological_order:
        unit = by_id[unit_id]
        chains: list[list[str]] = []
        if unit["declared_status"] == "SKIPPED_SAFEGUARD":
            chains.append([unit_id])
        for dependency_id in sorted(unit["depends_on"]):
            for dependency_chain in chains_by_id[dependency_id]:
                if len(chains) >= MAX_SKIP_CHAINS_PER_UNIT:
                    raise ValueError(
                        f"development unit {unit_id!r} exceeds maximum safeguard skip chains "
                        f"{MAX_SKIP_CHAINS_PER_UNIT}"
                    )
                chains.append([unit_id, *dependency_chain])
        chains_by_id[unit_id] = chains
    return chains_by_id


def _resolved_unit(
    unit: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    chains: list[list[str]],
) -> dict[str, Any]:
    skip_root_ids = sorted({chain[-1] for chain in chains})
    declared = unit["declared_status"]
    if declared == "SKIPPED_SAFEGUARD":
        effective = declared
    elif chains:
        effective = DERIVED_SKIPPED_STATE
    else:
        effective = declared

    metadata = {
        key: deepcopy(value)
        for key, value in unit.items()
        if key
        not in {
            "id",
            "title",
            "declared_status",
            "depends_on",
            "repercussions",
            "trigger",
        }
    }
    trigger = deepcopy(unit.get("trigger"))
    evidence = {
        "trigger": trigger,
        "historical_status": deepcopy(metadata.get("historical_status")),
        "evidence_refs": deepcopy(metadata.get("evidence_refs", [])),
    }
    return {
        "id": unit["id"],
        "title": unit["title"],
        "declared_status": declared,
        "effective_status": effective,
        "depends_on": list(unit["depends_on"]),
        "skip_root_ids": skip_root_ids,
        "skip_root_triggers": {root_id: deepcopy(by_id[root_id]["trigger"]) for root_id in skip_root_ids},
        "skip_dependency_chains": chains,
        "repercussions": list(unit["repercussions"]),
        "evidence": evidence,
        "trigger": trigger,
        "metadata": metadata,
    }
