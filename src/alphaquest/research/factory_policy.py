"""Deterministic pre-PnL identities shared by authoring and the local factory."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
import hashlib
import json
import re
from typing import Any, Mapping


LEGACY_RESEARCH_FACTORY_BINDING_SCHEMA = "alphaquest.research-factory-binding/v1"
RESEARCH_FACTORY_BINDING_SCHEMA = "alphaquest.research-factory-binding/v2"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_EVENT_ARTIFACT_HASH_FIELDS = (
    "archive_sha256",
    "raw_manifest_sha256",
    "session_levels_sha256",
    "quality_manifest_sha256",
    "concordance_report_sha256",
    "roll_calendar_sha256",
)


def research_objectives_sha256(objectives: Mapping[str, Any]) -> str:
    if not isinstance(objectives, Mapping):
        raise ValueError("research objectives must be a mapping")
    encoded = json.dumps(
        dict(objectives),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def research_factory_window_ids(objectives: Mapping[str, Any]) -> tuple[str, str]:
    """Return the two frozen logical windows available to one edge generation.

    The first identity is the current generation's acceptance window. The
    second is held in reserve for at most one fresh confirmation generation.
    A v2 compiled campaign additionally binds the first identity to exact
    calendar boundaries and governed data bytes. The confirmation identity
    remains logical because its data must not exist in the current generation.
    """

    objective_hash = research_objectives_sha256(objectives)
    prefix = objective_hash[:16]
    return (
        f"holdout_{prefix}_acceptance_01",
        f"holdout_{prefix}_confirmation_02",
    )


def research_factory_binding(
    objectives: Mapping[str, Any],
    *,
    dataset: Mapping[str, Any] | None = None,
    acceptance_train_months: int = 24,
    acceptance_test_months: int = 6,
) -> dict[str, Any]:
    """Build a frozen factory binding.

    Calls without ``dataset`` intentionally produce the legacy v1 logical
    binding. This supports read-only validation of historical campaigns and
    never upgrades them in place. Newly compiled campaigns supply their
    governed dataset and receive the v2 byte- and calendar-bound contract.
    """

    objective_hash = research_objectives_sha256(objectives)
    acceptance_window, confirmation_window = research_factory_window_ids(objectives)
    if dataset is None:
        return {
            "schema": LEGACY_RESEARCH_FACTORY_BINDING_SCHEMA,
            "research_objectives_sha256": objective_hash,
            "locked_holdout_window_id": acceptance_window,
        }

    dataset_binding = _dataset_binding(dataset)
    acceptance = _acceptance_window(
        dataset_binding["coverage_start"],
        dataset_binding["coverage_end"],
        train_months=acceptance_train_months,
        test_months=acceptance_test_months,
    )
    return {
        "schema": RESEARCH_FACTORY_BINDING_SCHEMA,
        "research_objectives_sha256": objective_hash,
        "locked_holdout_window_id": acceptance_window,
        "confirmation_holdout_window_id": confirmation_window,
        "dataset": dataset_binding,
        "acceptance_window": acceptance,
    }


def validate_research_factory_binding(
    value: Mapping[str, Any],
    *,
    objectives: Mapping[str, Any],
    dataset: Mapping[str, Any] | None = None,
    acceptance_train_months: int = 24,
    acceptance_test_months: int = 6,
) -> dict[str, Any]:
    """Validate current bindings while preserving historical v1 contracts."""

    if not isinstance(value, Mapping):
        raise ValueError("research_factory must be a mapping")
    observed = dict(value)
    schema = observed.get("schema")
    if schema == LEGACY_RESEARCH_FACTORY_BINDING_SCHEMA:
        expected = research_factory_binding(objectives)
    elif schema == RESEARCH_FACTORY_BINDING_SCHEMA:
        if dataset is None:
            raise ValueError(
                "research_factory v2 binding requires governed dataset identity and coverage"
            )
        expected = research_factory_binding(
            objectives,
            dataset=dataset,
            acceptance_train_months=acceptance_train_months,
            acceptance_test_months=acceptance_test_months,
        )
    else:
        raise ValueError("research_factory binding schema is missing or unsupported")

    if observed == expected:
        return expected
    objective_hash = str(observed.get("research_objectives_sha256") or "")
    if _SHA256.fullmatch(objective_hash) is None or objective_hash != expected["research_objectives_sha256"]:
        raise ValueError("research_factory objective hash is stale or mismatched")
    if observed.get("locked_holdout_window_id") != expected["locked_holdout_window_id"]:
        raise ValueError("research_factory locked-holdout window identity is stale or mismatched")
    if schema == RESEARCH_FACTORY_BINDING_SCHEMA:
        if observed.get("confirmation_holdout_window_id") != expected["confirmation_holdout_window_id"]:
            raise ValueError("research_factory confirmation-window identity is stale or mismatched")
        if observed.get("dataset") != expected["dataset"]:
            raise ValueError("research_factory governed dataset identity or bytes are stale or mismatched")
        if observed.get("acceptance_window") != expected["acceptance_window"]:
            raise ValueError("research_factory acceptance calendar is stale or mismatched")
    raise ValueError("research_factory locked-holdout binding is stale or mismatched")


def _dataset_binding(dataset: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(dataset, Mapping):
        raise ValueError("governed dataset identity must be a mapping")
    dataset_id = str(dataset.get("dataset_id") or "").strip()
    canonical_sha256 = str(dataset.get("canonical_sha256") or "").strip()
    source_sha256 = str(dataset.get("source_sha256") or "").strip()
    coverage_start = str(dataset.get("coverage_start") or "").strip()
    coverage_end = str(dataset.get("coverage_end") or "").strip()
    if not dataset_id:
        raise ValueError("governed dataset identity requires dataset_id")
    if _SHA256.fullmatch(canonical_sha256) is None:
        raise ValueError("governed dataset identity requires canonical_sha256")
    if _SHA256.fullmatch(source_sha256) is None:
        raise ValueError("governed dataset identity requires source_sha256")
    _parse_iso_date(coverage_start, field="coverage_start")
    _parse_iso_date(coverage_end, field="coverage_end")

    binding: dict[str, Any] = {
        "dataset_id": dataset_id,
        "canonical_sha256": canonical_sha256,
        "source_sha256": source_sha256,
        "coverage_start": coverage_start,
        "coverage_end": coverage_end,
    }
    roll_hash = dataset.get("roll_calendar_sha256")
    if roll_hash is not None:
        normalized_roll_hash = str(roll_hash).strip()
        if _SHA256.fullmatch(normalized_roll_hash) is None:
            raise ValueError("governed dataset roll_calendar_sha256 is invalid")
        binding["roll_calendar_sha256"] = normalized_roll_hash

    event_source = dataset.get("event_source")
    if event_source is None:
        event_source = dataset.get("execution_data")
    if event_source is not None:
        if not isinstance(event_source, Mapping):
            raise ValueError("governed event execution source must be a mapping")
        event_document = {
            str(key): value for key, value in event_source.items() if value is not None
        }
        artifact_hashes = {
            field: str(event_document[field])
            for field in _EVENT_ARTIFACT_HASH_FIELDS
            if event_document.get(field) is not None
        }
        if not artifact_hashes or any(
            _SHA256.fullmatch(value) is None for value in artifact_hashes.values()
        ):
            raise ValueError(
                "governed event execution source requires valid artifact byte hashes"
            )
        binding["event_execution_contract_sha256"] = _object_sha256(event_document)
        binding["event_execution_artifact_sha256s"] = artifact_hashes
    return binding


def _acceptance_window(
    coverage_start: str,
    coverage_end: str,
    *,
    train_months: int,
    test_months: int,
) -> dict[str, Any]:
    if train_months <= 0 or test_months <= 0:
        raise ValueError("acceptance train and test months must be greater than zero")
    first = _parse_iso_date(coverage_start, field="coverage_start")
    test_end = _parse_iso_date(coverage_end, field="coverage_end")
    if test_end < first:
        raise ValueError("governed dataset coverage_end cannot precede coverage_start")
    test_start = _subtract_calendar_months(test_end, test_months)
    train_start = _subtract_calendar_months(test_start, train_months)
    if first > train_start:
        raise ValueError(
            "governed dataset does not cover the complete predeclared acceptance train and test calendar"
        )
    return {
        "train_months": train_months,
        "test_months": test_months,
        "train_start": train_start.isoformat(),
        "train_end": (test_start - timedelta(days=1)).isoformat(),
        "test_start": test_start.isoformat(),
        "test_end": test_end.isoformat(),
    }


def _subtract_calendar_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 - months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _parse_iso_date(value: str, *, field: str) -> date:
    try:
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"governed dataset {field} must start with an ISO date") from exc


def _object_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "LEGACY_RESEARCH_FACTORY_BINDING_SCHEMA",
    "RESEARCH_FACTORY_BINDING_SCHEMA",
    "research_factory_binding",
    "research_factory_window_ids",
    "research_objectives_sha256",
    "validate_research_factory_binding",
]
