"""Build a fail-closed index for one completed diagnostic pre-acceptance run.

This module is deliberately report-only.  It neither launches research stages nor
creates or approves any research-governance decision.
"""

from __future__ import annotations

import argparse
import ast
import csv
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pyarrow.parquet as pq
import pandas as pd
from pydantic import TypeAdapter
import yaml

from alphaquest.backtest.contracts import ExecutionAssumptions
from alphaquest.authoring.models import (
    CERTIFIED_RECIPE_BINDINGS,
    DatasetManifestV1,
    ExecutionSettingsV1,
    ModuleBindingV1,
    SequentialVariantLineageV1,
    Sha256,
    _binding_structure,
)
from alphaquest.dashboard.validation_app import load_manual_reviews, trade_id_key
from alphaquest.prop.profiles import resolve_prop_profile
from alphaquest.research.campaign_stages import (
    ACCEPTANCE_STAGE,
    DEFAULT_STAGE_CRITERIA,
    PRE_ACCEPTANCE_STAGE_ORDER,
    STAGE_LABELS,
    _annotate_stage_decisions,
    _first_failed_stage,
    _merged_section,
    _research_verdict,
    _scientific_validity_verdict,
    _select_incubation_params,
    _skipped_stage,
    apply_authoritative_parallel_defaults,
    canonicalize_campaign_config,
    evaluate_criteria,
)
from alphaquest.research.core_grid import _expected_combination_count, parameter_combinations
from alphaquest.research.preflight import run_preflight
from alphaquest.research.schemas import (
    validate_campaign_config_contract,
    validate_run_summary_contract,
    validate_stage_result_contract,
)
from alphaquest.research.storage import (
    load_storage_layout,
    resolve_campaign_context,
    resolve_recorded_path,
)
from alphaquest.research.wfa import (
    _objective_label,
    _select_best_in_sample,
    _selection_sort_spec,
    _train_grid_metadata,
    _validate_oos_intervals,
    _validate_stitched_oos_trade_identity,
    _wfa_grid_config,
    _wfa_mode,
)
from alphaquest.studio.approvals import MechanicsApprovalService
from alphaquest.utils.config import strategy_mechanic, validate_campaign_run_root
from alphaquest.utils.hashing import file_sha256, object_sha256
from alphaquest.validation.promotion_gate import (
    APPROVAL_SCHEMA,
    REQUIRED_SAMPLE_CATEGORIES,
    inspect_validation_gate,
)
from alphaquest.validation.schema import (
    BAR_WINDOWS_FILENAME,
    CONDITION_SNAPSHOTS_FILENAME,
    EVENT_TRANSITIONS_FILENAME,
    EXIT_AUDITS_FILENAME,
    TICK_WINDOWS_FILENAME,
    TRADES_FILENAME,
    VALIDATION_CHECKS_FILENAME,
)
from alphaquest.version import ENGINE_CONTRACT_VERSION


SCHEMA = "alphaquest.mvp-diagnostic-index/v1"
DIAGNOSTIC_REASON = f"mandatory {ACCEPTANCE_STAGE} was omitted"
_DURATION_TOLERANCE_SECONDS = 0.000001
_SHA256_ADAPTER = TypeAdapter(Sha256)
_IDENTITY_FIELDS = (
    "run_uid",
    "campaign_id",
    "variant_id",
    "test_run_id",
    "attempt_id",
    "attempt_kind",
    "attempt_provenance",
    "parent_attempt_id",
    "symbol",
    "dataset_id",
)
_REQUIRED_IDENTITY_FIELDS = tuple(field for field in _IDENTITY_FIELDS if field != "parent_attempt_id")
_CANONICAL_STAGE_SUMMARIES = {
    "limited_core_grid_test": "core_grid_summary.json",
    "limited_monkey_test": "monkey_summary.json",
    "walk_forward_analysis": "wfa_summary.json",
    "wfa_oos_monkey_test": "wfa_oos_monkey_summary.json",
    "wfa_oos_monte_carlo": "wfa_oos_monte_carlo_summary.json",
    "simulated_incubation_core": "incubation_oos_summary.json",
    "simulated_incubation_monkey": "incubation_monkey_summary.json",
}
_COMPLETED_STAGE_PAYLOAD_KEYS = {
    "limited_core_grid_test": {"summary", "data_quality", "input_hash", "artifacts", "core_grid_parameters"},
    "limited_monkey_test": {
        "summary",
        "data_quality",
        "input_hash",
        "selected_core_params",
        "selected_core_row",
        "artifacts",
    },
    "walk_forward_analysis": {
        "summary",
        "stitched_oos_metrics",
        "incubation_selected_params",
        "data_quality",
        "input_hash",
        "artifacts",
    },
    "wfa_oos_monkey_test": {"summary", "artifacts"},
    "wfa_oos_monte_carlo": {"summary", "artifacts"},
    "simulated_incubation_core": {
        "summary",
        "metrics",
        "diagnostics",
        "selected_params",
        "incubation_train_selection",
        "data_quality",
        "input_hash",
        "artifacts",
    },
    "simulated_incubation_monkey": {"summary", "artifacts"},
}
_STAGE_COMMON_KEYS = {
    "stage",
    "label",
    "status",
    "passed",
    "started_at",
    "completed_at",
    "duration_seconds",
    "criteria",
    "scientific_validity_verdict",
    "scientific_validity_passed",
    "generic_objective_verdict",
    "generic_objective_passed",
}
_DATA_BEARING_STAGES = {
    "limited_core_grid_test",
    "limited_monkey_test",
    "walk_forward_analysis",
    "simulated_incubation_core",
}
_UNVERIFIED_DATA_QUALITY_FIELDS = {"prepare_data_duration_seconds", "prepared_data_cache"}
_MECHANICS_ARTIFACT_FILES = {
    "trades": TRADES_FILENAME,
    "condition_snapshots": CONDITION_SNAPSHOTS_FILENAME,
    "bar_windows": BAR_WINDOWS_FILENAME,
    "tick_windows": TICK_WINDOWS_FILENAME,
    "event_transitions": EVENT_TRANSITIONS_FILENAME,
    "exit_audits": EXIT_AUDITS_FILENAME,
    "validation_checks": VALIDATION_CHECKS_FILENAME,
}
_CAMPAIGN_DOCUMENT_KEYS = {
    "campaign_id",
    "title",
    "status",
    "created_at",
    "instrument",
    "timeframe",
    "governance_contract_version",
    "variant_protocol",
    "max_variants",
    "research_objectives",
    "research_objectives_sha256",
    "research_factory",
    "authoring_lane",
    "certified_recipe",
    "event_strategy",
    "event_strategies",
    "edge_family",
    "hypothesis",
    "economic_edge_fingerprint",
    "duplicate_edge_review",
    "sources",
    "variants",
    "sequential_variant_history",
    "variant_distinctions",
    "rescue_policy",
}
_STRATEGY_SPEC_KEYS = {
    "schema",
    "campaign_id",
    "draft_sha256",
    "research_objectives",
    "research_objectives_sha256",
    "research_factory",
    "frozen",
    "hypothesis",
    "expected_mechanism",
    "holding_horizon",
    "known_failure_modes",
    "authoring_lane",
    "certified_recipe",
    "event_strategy",
    "strategy_certification",
    "variant_strategy_certifications",
    "dataset",
    "execution",
    "variants",
}
_STRATEGY_SPEC_VARIANT_KEYS = {
    "variant_id",
    "title",
    "mechanic_signature",
    "entry",
    "stop",
    "target",
    "event_parameter_grid",
    "rationales",
}
_AUTHORING_MANIFEST_KEYS = {
    "schema",
    "campaign_id",
    "draft_schema",
    "draft_sha256",
    "research_objectives_sha256",
    "research_factory",
    "dataset_id",
    "dataset_canonical_sha256",
    "authoring_lane",
    "certified_recipe",
    "event_strategy",
    "strategy_certification",
    "variant_strategy_certifications",
    "compiler",
    "created_at",
    "variant_count",
    "variant_protocol",
    "max_variants",
    "variant_mechanic_signatures",
    "compiled_document_sha256",
    "planned_files",
    "generated_python_stubs",
}


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing required {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid {label} at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return value


def _read_yaml(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing required {label}: {path}")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"invalid {label} at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a YAML mapping: {path}")
    return value


def _artifact(path: Path, *, project_root: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"required artifact is not a file: {path}")
    try:
        display = path.resolve().relative_to(project_root).as_posix()
    except ValueError:
        display = str(path.resolve())
    return {"path": display, "sha256": file_sha256(path), "bytes": path.stat().st_size}


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, found {actual!r}")


def _require_exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    _require_equal(set(value), expected, f"{label} fields")
    return value


def _require_sha256(value: Any, label: str) -> str:
    try:
        return _SHA256_ADAPTER.validate_python(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a lowercase SHA-256") from exc


def _require_iso_date(value: Any, label: str) -> str:
    text = _require_nonempty_string(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be a valid YYYY-MM-DD date") from exc
    _require_equal(text, parsed.isoformat(), label)
    return text


def _require_aware_datetime(value: Any, label: str) -> datetime:
    text = _require_nonempty_string(value, label)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return parsed


def _frozen_stage_criteria(stage_name: str, stage_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    configured = stage_cfg.get("criteria")
    if not isinstance(configured, list) or not configured or not all(isinstance(item, dict) for item in configured):
        raise ValueError(f"{stage_name} frozen criteria must be a non-empty list of mappings")
    metrics = [item.get("metric") for item in configured]
    if len(metrics) != len(set(metrics)):
        raise ValueError(f"{stage_name} frozen criteria contain duplicate metrics")
    by_metric = {item.get("metric"): item for item in configured}
    for baseline in DEFAULT_STAGE_CRITERIA.get(stage_name, []):
        metric = baseline["metric"]
        observed = by_metric.get(metric)
        if observed is None:
            raise ValueError(f"{stage_name} frozen criteria omit repository criterion {metric}")
        for field, expected in baseline.items():
            if field in {"metric", "source"}:
                continue
            actual = observed.get(field)
            if field in {"min", "exclusive_min"}:
                if (
                    isinstance(actual, bool)
                    or not isinstance(actual, (int, float))
                    or not math.isfinite(float(actual))
                    or float(actual) < float(expected)
                ):
                    raise ValueError(f"{stage_name} frozen criterion {metric} weakens repository {field}")
            elif field in {"max", "exclusive_max"}:
                if (
                    isinstance(actual, bool)
                    or not isinstance(actual, (int, float))
                    or not math.isfinite(float(actual))
                    or float(actual) > float(expected)
                ):
                    raise ValueError(f"{stage_name} frozen criterion {metric} weakens repository {field}")
            elif actual != expected:
                raise ValueError(f"{stage_name} frozen criterion {metric} changes repository {field}")
    return deepcopy(configured)


def _validate_campaign_research_contract(campaign: dict[str, Any]) -> None:
    _require_exact_keys(campaign, _CAMPAIGN_DOCUMENT_KEYS, "campaign document")
    _require_iso_date(campaign.get("created_at"), "campaign created_at")
    sources = campaign.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("campaign sources must be a non-empty list")
    source_fields = {"title", "authors", "year", "link", "doi", "relevance"}
    for index, item in enumerate(sources):
        source = _require_exact_keys(item, source_fields, f"campaign source {index}")
        for field in ("title", "authors", "relevance"):
            _require_nonempty_string(source.get(field), f"campaign source {index} {field}")
        year = source.get("year")
        if isinstance(year, bool) or not isinstance(year, int) or not 1900 <= year <= 2200:
            raise ValueError(f"campaign source {index} year is invalid")
        if not any(isinstance(source.get(field), str) and source[field].strip() for field in ("link", "doi")):
            raise ValueError(f"campaign source {index} requires link or DOI")

    fingerprint = _require_exact_keys(
        campaign.get("economic_edge_fingerprint"),
        {"market_behavior", "causal_mechanism", "signal_inputs", "market_context", "holding_period"},
        "campaign economic edge fingerprint",
    )
    for field, value in fingerprint.items():
        _require_nonempty_string(value, f"campaign economic edge fingerprint {field}")

    duplicate = _require_exact_keys(
        campaign.get("duplicate_edge_review"),
        {"reviewed_campaign_ids", "ledger_queries", "conclusion", "substantive_distinction"},
        "campaign duplicate review",
    )
    if not isinstance(duplicate.get("reviewed_campaign_ids"), list) or not all(
        isinstance(value, str) and value.strip() for value in duplicate["reviewed_campaign_ids"]
    ):
        raise ValueError("campaign duplicate review IDs must be strings")
    if (
        not isinstance(duplicate.get("ledger_queries"), list)
        or not duplicate["ledger_queries"]
        or not all(isinstance(value, str) and value.strip() for value in duplicate["ledger_queries"])
    ):
        raise ValueError("campaign duplicate review ledger queries must be non-empty strings")
    _require_equal(duplicate.get("conclusion"), "distinct", "campaign duplicate review conclusion")
    _require_nonempty_string(duplicate.get("substantive_distinction"), "campaign duplicate substantive distinction")

    history = campaign.get("sequential_variant_history")
    if not isinstance(history, list):
        raise ValueError("campaign sequential variant history must be a list")
    for index, item in enumerate(history):
        try:
            model = SequentialVariantLineageV1.model_validate(item)
        except ValueError as exc:
            raise ValueError(f"campaign sequential variant history {index} is invalid: {exc}") from exc
        _require_equal(item, model.model_dump(mode="json", by_alias=True), f"campaign sequential history {index}")

    variants = campaign.get("variants")
    distinctions = campaign.get("variant_distinctions")
    if (
        not isinstance(variants, list)
        or not variants
        or not all(isinstance(value, str) and value for value in variants)
    ):
        raise ValueError("campaign variants must be non-empty string identities")
    if campaign.get("variant_protocol") == "sequential_failure_informed":
        _require_equal(len(history), max(0, len(variants) - 1), "campaign sequential history count")
    elif campaign.get("variant_protocol") == "legacy_predeclared":
        _require_equal(history, [], "legacy campaign sequential history")
    else:
        raise ValueError("campaign variant protocol is unsupported")
    for index, lineage in enumerate(history, start=1):
        _require_equal(lineage.get("variant_id"), variants[index], f"campaign sequential variant {index}")
        _require_equal(
            lineage.get("predecessor_variant_id"), variants[index - 1], f"campaign sequential predecessor {index}"
        )
    if not isinstance(distinctions, dict):
        raise ValueError("campaign variant distinctions must be a mapping")
    _require_equal(set(distinctions), set(variants), "campaign variant distinction identities")
    for variant_id, item in distinctions.items():
        distinction = _require_exact_keys(
            item,
            {"mechanic", "material_difference", "mechanic_signature"},
            f"campaign variant distinction {variant_id}",
        )
        for field, value in distinction.items():
            _require_nonempty_string(value, f"campaign variant distinction {variant_id} {field}")


def _validate_strategy_spec_contract(strategy_spec: dict[str, Any]) -> None:
    _require_exact_keys(strategy_spec, _STRATEGY_SPEC_KEYS, "strategy spec")
    for field in ("hypothesis", "expected_mechanism", "holding_horizon"):
        _require_nonempty_string(strategy_spec.get(field), f"strategy spec {field}")
    failures = strategy_spec.get("known_failure_modes")
    if (
        not isinstance(failures, list)
        or not failures
        or not all(isinstance(value, str) and value.strip() for value in failures)
    ):
        raise ValueError("strategy spec known failure modes must be non-empty strings")
    variants = strategy_spec.get("variants")
    if not isinstance(variants, list) or not variants:
        raise ValueError("strategy spec variants must be a non-empty list")
    for index, item in enumerate(variants):
        _require_exact_keys(item, _STRATEGY_SPEC_VARIANT_KEYS, f"strategy spec variant {index}")


def _compiled_object_sha256(value: Any) -> str:
    """Match CampaignCompiler's canonical object hash for published documents."""

    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalized_paths(values: Any, project_root: Path, label: str) -> list[Path]:
    if not isinstance(values, list):
        raise ValueError(f"{label} must be a list")
    return [_resolve_reference(value, project_root, f"{label}[{index}]") for index, value in enumerate(values)]


def _resolve_reference(value: Any, project_root: Path, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing required {label} path")
    return resolve_recorded_path(value, project_root=project_root).resolve()


def _inventory_run(run_dir: Path, project_root: Path) -> list[dict[str, Any]]:
    files = sorted(path for path in run_dir.rglob("*") if path.is_file())
    if not files:
        raise ValueError(f"run directory contains no artifacts: {run_dir}")
    return [_artifact(path, project_root=project_root) for path in files]


def _require_nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _trade_id_key(value: Any, label: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f"{label} must be a string or integer trade ID")
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"{label} must not be empty")
    key = trade_id_key(value)
    if not key:
        raise ValueError(f"{label} must have a canonical trade identity")
    return key


def _validate_approval_sampling(approval: dict[str, Any], evidence_dir: Path) -> None:
    sampled = approval.get("sampled_trade_ids")
    categories = approval.get("sampling_categories")
    reasons = approval.get("sampling_reasons")
    if not isinstance(sampled, list) or not isinstance(categories, dict) or not isinstance(reasons, dict):
        raise ValueError("mechanics approval sampling structure is incomplete")
    sampled_keys = [_trade_id_key(value, "sampled_trade_ids") for value in sampled]
    if len(sampled_keys) != len(set(sampled_keys)):
        raise ValueError("mechanics approval sampled_trade_ids must be unique")
    _require_equal(set(categories), set(REQUIRED_SAMPLE_CATEGORIES), "mechanics approval category set")
    ordered: list[Any] = []
    seen: set[str] = set()
    for category in REQUIRED_SAMPLE_CATEGORIES:
        values = categories.get(category)
        if not isinstance(values, list):
            raise ValueError(f"mechanics approval category {category} must be a list")
        category_keys = [_trade_id_key(value, f"sampling_categories.{category}") for value in values]
        if len(category_keys) != len(set(category_keys)):
            raise ValueError(f"mechanics approval category {category} contains duplicate IDs")
        for value, key in zip(values, category_keys, strict=True):
            if key not in seen:
                ordered.append(value)
                seen.add(key)
    _require_equal(sampled, ordered, "mechanics approval sampled/category ordered union")

    metadata = _read_json(evidence_dir / "metadata.json", "mechanics evidence metadata")
    source_trade_count = metadata.get("source_trade_count")
    requested = approval.get("fixed_random_sample_size")
    if isinstance(source_trade_count, bool) or not isinstance(source_trade_count, int) or source_trade_count < 0:
        raise ValueError("mechanics evidence source_trade_count must be a non-negative integer")
    if isinstance(requested, bool) or not isinstance(requested, int) or requested < 1:
        raise ValueError("mechanics approval fixed_random_sample_size must be a positive integer")
    _require_equal(
        len(categories["random_trades"]),
        min(requested, source_trade_count),
        "mechanics approval random sample count",
    )
    reason_keys = {_trade_id_key(value, "sampling_reasons") for value in sampled}
    canonical_reason_keys = [_trade_id_key(value, "sampling_reasons") for value in reasons]
    if len(canonical_reason_keys) != len(set(canonical_reason_keys)):
        raise ValueError("mechanics approval sampling reason IDs must be unique")
    _require_equal(set(canonical_reason_keys), reason_keys, "mechanics approval sampling reason IDs")
    for trade_id, values in reasons.items():
        if (
            not isinstance(values, list)
            or not values
            or not all(isinstance(value, str) and value.strip() for value in values)
        ):
            raise ValueError(f"mechanics approval sampling reasons for {trade_id} must be non-empty strings")
        if len(values) != len(set(values)):
            raise ValueError(f"mechanics approval sampling reasons for {trade_id} must be unique")


def _require_run_location(
    run_dir: Path,
    *,
    project_root: Path,
    effective_config: dict[str, Any],
    effective_path: Path,
) -> None:
    layout = load_storage_layout(project_root)
    if not any(_is_relative_to(run_dir, evidence_root.resolve()) for evidence_root in layout.evidence_roots):
        raise ValueError("run directory must be below a configured evidence root")
    validate_campaign_run_root(run_dir, effective_config, config_path=effective_path)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _config_identity(config: dict[str, Any]) -> dict[str, Any]:
    data = config.get("data") if isinstance(config.get("data"), dict) else {}
    return {
        "campaign_id": config.get("campaign_id"),
        "variant_id": config.get("variant_id"),
        "test_run_id": config.get("test_run_id"),
        "attempt_id": config.get("attempt_id"),
        "attempt_kind": config.get("attempt_kind"),
        "attempt_provenance": config.get("attempt_provenance"),
        "parent_attempt_id": config.get("parent_attempt_id"),
        "symbol": config.get("symbol") or data.get("symbol"),
        "dataset_id": config.get("dataset_id") or data.get("dataset_id"),
        "timeframe": config.get("timeframe") or data.get("timeframe") or data.get("source_timeframe"),
    }


def _bind_identities(
    source_config: dict[str, Any],
    effective_config: dict[str, Any],
    summary: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    source_identity = _config_identity(source_config)
    effective_identity = _config_identity(effective_config)
    for field in _REQUIRED_IDENTITY_FIELDS:
        _require_nonempty_string(summary.get(field), f"summary.{field}")
        _require_equal(manifest.get(field), summary.get(field), f"manifest {field}")
    _require_nonempty_string(summary.get("timeframe"), "summary.timeframe")
    _require_equal(manifest.get("timeframe"), summary.get("timeframe"), "manifest timeframe")
    for field in (*_REQUIRED_IDENTITY_FIELDS[1:], "parent_attempt_id", "timeframe"):
        _require_equal(source_identity.get(field), summary.get(field), f"source config {field}")
        _require_equal(effective_identity.get(field), summary.get(field), f"effective config {field}")
    _require_equal(manifest.get("parent_attempt_id"), summary.get("parent_attempt_id"), "manifest parent_attempt_id")
    _require_equal(summary.get("attempt_provenance"), "authored", "attempt provenance")
    if summary.get("attempt_kind") == "original":
        _require_equal(summary.get("parent_attempt_id"), None, "original attempt parent")
    elif not isinstance(summary.get("parent_attempt_id"), str) or not summary["parent_attempt_id"].strip():
        raise ValueError("non-original attempt requires a non-empty parent_attempt_id")


def _expected_effective_config(source_config: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    expected = canonicalize_campaign_config(source_config, include_acceptance=False)
    workers = summary.get("authoritative_parallel_workers")
    core_workers = summary.get("authoritative_core_grid_workers")
    if workers is None and core_workers is not None:
        raise ValueError("authoritative_core_grid_workers requires authoritative_parallel_workers")
    if workers is not None:
        if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
            raise ValueError("authoritative_parallel_workers must be a positive integer or null")
        if core_workers is not None and (
            isinstance(core_workers, bool) or not isinstance(core_workers, int) or core_workers < 1
        ):
            raise ValueError("authoritative_core_grid_workers must be a positive integer or null")
        expected = apply_authoritative_parallel_defaults(
            expected,
            workers=workers,
            core_grid_workers=core_workers,
        )
    return expected


def _validate_authoring_execution(
    execution_value: Any,
    source_config: dict[str, Any],
) -> dict[str, Any]:
    try:
        execution = ExecutionSettingsV1.model_validate(execution_value)
    except ValueError as exc:
        raise ValueError(f"strategy spec execution contract failed: {exc}") from exc
    document = execution.model_dump(mode="json")
    _require_equal(execution_value, document, "strategy spec execution document")
    data = source_config.get("data") or {}
    core = source_config.get("core") or {}
    apex = source_config.get("apex_rules") or {}
    strategy = source_config.get("strategy") or {}
    position = core.get("position_sizing") or {}
    shared = {
        "session_start": data.get("rth_start"),
        "session_end": data.get("rth_end"),
        "latest_entry_time": apex.get("latest_entry_time"),
        "flatten_time": apex.get("force_flatten_time"),
        "latest_flat_time": apex.get("latest_flat_time"),
        "overnight_allowed": not bool(apex.get("no_overnight_positions")),
        "initial_balance": core.get("initial_balance"),
        "tick_size": core.get("tick_size"),
        "point_value": core.get("point_value"),
        "tick_value": core.get("tick_value"),
        "commission_per_contract": core.get("commission_per_contract"),
        "slippage_ticks": core.get("slippage_ticks"),
        "contracts": position.get("contracts"),
    }
    for field, expected in shared.items():
        _require_equal(document.get(field), expected, f"strategy spec execution {field}")
    safety_controls = {
        "enabled": True,
        "timezone": data.get("exchange_timezone"),
        "force_flatten_enabled": True,
        "cancel_pending_orders_before_flatten": True,
        "no_overnight_positions": not document["overnight_allowed"],
        "reject_if_position_after_flatten_deadline": True,
        "reject_if_pending_order_after_flatten_deadline": True,
        "reject_if_entry_after_latest_entry_time": True,
    }
    for field, expected in safety_controls.items():
        _require_equal(apex.get(field), expected, f"compiled execution safety {field}")
    _require_equal(position.get("mode"), "fixed_contracts", "compiled position sizing mode")
    _require_equal(core.get("max_trades_per_day"), 1, "compiled maximum trades per day")
    _require_equal(strategy.get("flatten_time"), document["flatten_time"], "strategy execution flatten time")
    _require_equal(core.get("flatten_time"), document["flatten_time"], "core execution flatten time")
    expected_prop_rules = resolve_prop_profile(
        document["prop_profile"],
        starting_balance=document["initial_balance"],
        max_contracts=document["contracts"],
        force_flatten_time=document["flatten_time"],
    )
    _require_equal(source_config.get("prop_rules"), expected_prop_rules, "compiled prop profile")
    bindings = source_config.get("account_profile_bindings") or []
    if not isinstance(bindings, list) or not all(isinstance(item, dict) for item in bindings):
        raise ValueError("compiled account profile bindings must be a list of mappings")
    selections = [
        {"profile_id": item.get("profile_id"), "version": item.get("version"), "role": item.get("role")}
        for item in bindings
    ]
    _require_equal(document.get("target_account_profiles"), selections, "compiled target account profiles")
    return document


def _authoring_binding(
    source_path: Path,
    source_config: dict[str, Any],
    dataset_manifest: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    context = resolve_campaign_context(source_path, project_root=project_root)
    if context is None or context.lifecycle != "active":
        raise ValueError("source config must belong to a published active campaign")
    manifest_path = context.campaign_root / "authoring_manifest.json"
    authoring = _read_json(manifest_path, "authoring manifest")
    _require_exact_keys(authoring, _AUTHORING_MANIFEST_KEYS, "authoring manifest")
    _require_equal(authoring.get("schema"), "alphaquest.authoring-manifest/v1", "authoring manifest schema")
    _require_equal(authoring.get("compiler"), "alphaquest.authoring.CampaignCompiler/v1", "authoring compiler")
    _require_equal(authoring.get("generated_python_stubs"), False, "authoring generated Python stubs")
    _require_equal(authoring.get("draft_schema"), "alphaquest.campaign-draft/v1", "authoring draft schema")
    _require_equal(authoring.get("campaign_id"), source_config.get("campaign_id"), "authoring campaign")
    _require_equal(authoring.get("authoring_lane"), "certified_recipe", "authoring lane")
    _require_iso_date(authoring.get("created_at"), "authoring created_at")
    _require_sha256(authoring.get("draft_sha256"), "authoring draft_sha256")
    recipe = _require_nonempty_string(authoring.get("certified_recipe"), "authoring certified_recipe")
    if recipe not in CERTIFIED_RECIPE_BINDINGS:
        raise ValueError(f"unsupported certified recipe: {recipe}")
    expected_entry, expected_setup = CERTIFIED_RECIPE_BINDINGS[recipe]
    entry = (source_config.get("strategy") or {}).get("entry") or {}
    _require_equal(entry.get("module"), expected_entry, "certified recipe entry module")
    if expected_setup is not None:
        _require_equal((entry.get("params") or {}).get("setup_mode"), expected_setup, "certified recipe setup mode")
    _require_equal(authoring.get("dataset_id"), _config_identity(source_config)["dataset_id"], "authoring dataset")
    _require_equal(
        authoring.get("dataset_canonical_sha256"),
        dataset_manifest.get("canonical_sha256"),
        "authoring dataset canonical hash",
    )
    variant_id = _require_nonempty_string(source_config.get("variant_id"), "source config variant_id")
    expected_compiled = {
        "campaign.yaml",
        "strategy_spec.yaml",
        f"variants/{variant_id}/config.yaml",
    }
    _require_equal(authoring.get("variant_count"), 1, "authoring variant count")
    _require_equal(
        authoring.get("planned_files"),
        ["campaign.yaml", "strategy_spec.yaml", "authoring_manifest.json", f"variants/{variant_id}/config.yaml"],
        "authoring planned files",
    )
    compiled = authoring.get("compiled_document_sha256")
    if not isinstance(compiled, dict):
        raise ValueError("authoring manifest lacks compiled document hashes")
    _require_equal(set(compiled), expected_compiled, "authoring compiled document topology")
    config_relative = source_path.relative_to(context.campaign_root).as_posix()
    _require_equal(
        compiled.get(config_relative),
        _compiled_object_sha256(source_config),
        "published source config hash",
    )
    documents: list[dict[str, Any]] = []
    parsed_documents: dict[str, dict[str, Any]] = {}
    for relative, expected_hash in sorted(compiled.items()):
        document_path = context.campaign_root / str(relative)
        artifact = _artifact(document_path, project_root=project_root)
        document = _read_yaml(document_path, f"published document {relative}")
        parsed_documents[relative] = document
        compiled_object_sha256 = _compiled_object_sha256(document)
        _require_equal(
            compiled_object_sha256,
            expected_hash,
            f"published document {relative} hash",
        )
        documents.append(
            {
                "path": artifact["path"],
                "file_sha256": artifact["sha256"],
                "bytes": artifact["bytes"],
                "compiled_object_sha256": compiled_object_sha256,
            }
        )
    campaign = parsed_documents["campaign.yaml"]
    strategy_spec = parsed_documents["strategy_spec.yaml"]
    _validate_campaign_research_contract(campaign)
    _validate_strategy_spec_contract(strategy_spec)
    _require_equal(campaign.get("campaign_id"), source_config.get("campaign_id"), "campaign document identity")
    _require_equal(campaign.get("status"), "authored_for_testing", "campaign authored status")
    _require_nonempty_string(campaign.get("title"), "campaign title")
    _require_nonempty_string(campaign.get("edge_family"), "campaign edge_family")
    _require_equal(campaign.get("authoring_lane"), "certified_recipe", "campaign authoring lane")
    _require_equal(campaign.get("certified_recipe"), recipe, "campaign certified recipe")
    _require_equal(
        campaign.get("instrument") or campaign.get("symbol"), source_config.get("symbol"), "campaign instrument"
    )
    _require_equal(campaign.get("timeframe"), source_config.get("timeframe"), "campaign timeframe")
    _require_equal(campaign.get("variants"), [variant_id], "campaign variant list")
    _require_equal(
        campaign.get("governance_contract_version"),
        3 if campaign.get("variant_protocol") == "sequential_failure_informed" else 2,
        "campaign governance contract",
    )
    _require_equal(campaign.get("event_strategies"), {}, "campaign event strategy map")
    _require_equal(campaign.get("event_strategy"), None, "certified recipe campaign event strategy")
    _require_equal(
        campaign.get("rescue_policy"),
        {"allowed": False, "max_rescues_per_failed_variant": 1},
        "campaign rescue policy",
    )
    _require_equal(
        campaign.get("max_variants"),
        (source_config.get("research_objectives") or {}).get("maximum_variants"),
        "campaign maximum variants",
    )
    _require_equal(strategy_spec.get("schema"), "alphaquest.strategy-spec/v1", "strategy spec schema")
    _require_equal(strategy_spec.get("frozen"), True, "strategy spec frozen flag")
    _require_equal(strategy_spec.get("campaign_id"), source_config.get("campaign_id"), "strategy spec identity")
    _require_equal(strategy_spec.get("authoring_lane"), "certified_recipe", "strategy spec authoring lane")
    _require_equal(strategy_spec.get("certified_recipe"), recipe, "strategy spec certified recipe")
    _require_sha256(strategy_spec.get("draft_sha256"), "strategy spec draft_sha256")
    _require_equal(strategy_spec.get("event_strategy"), None, "certified recipe strategy event strategy")
    _require_equal(strategy_spec.get("strategy_certification"), None, "certified recipe strategy certification")
    _require_equal(
        strategy_spec.get("variant_strategy_certifications"),
        {},
        "certified recipe variant strategy certifications",
    )
    _require_equal(authoring.get("event_strategy"), None, "certified recipe authoring event strategy")
    _require_equal(authoring.get("strategy_certification"), None, "certified recipe authoring certification")
    _require_equal(
        authoring.get("variant_strategy_certifications"),
        {},
        "certified recipe authoring variant certifications",
    )
    _require_equal(strategy_spec.get("dataset"), dataset_manifest, "strategy spec dataset")
    execution = _validate_authoring_execution(strategy_spec.get("execution"), source_config)
    for field in ("research_objectives", "research_objectives_sha256", "event_strategy"):
        _require_equal(campaign.get(field), source_config.get(field), f"campaign {field}")
        _require_equal(strategy_spec.get(field), source_config.get(field), f"strategy spec {field}")
    for field in ("research_objectives_sha256", "event_strategy"):
        _require_equal(authoring.get(field), source_config.get(field), f"authoring {field}")
    _require_equal(authoring.get("draft_sha256"), strategy_spec.get("draft_sha256"), "authoring draft hash")
    _require_equal(authoring.get("created_at"), campaign.get("created_at"), "authoring created_at")
    _require_equal(authoring.get("variant_protocol"), campaign.get("variant_protocol"), "authoring variant protocol")
    _require_equal(
        authoring.get("max_variants"),
        (source_config.get("research_objectives") or {}).get("maximum_variants"),
        "authoring maximum variants",
    )
    for field in ("strategy_certification", "variant_strategy_certifications"):
        _require_equal(authoring.get(field), strategy_spec.get(field), f"authoring {field}")
    for container_name, container in (
        ("campaign", campaign),
        ("strategy spec", strategy_spec),
        ("authoring manifest", authoring),
    ):
        _require_equal(
            container.get("research_factory"),
            source_config.get("research_factory"),
            f"{container_name} research factory",
        )
    spec_variants = strategy_spec.get("variants")
    if not isinstance(spec_variants, list) or len(spec_variants) != 1 or not isinstance(spec_variants[0], dict):
        raise ValueError("strategy spec must contain exactly one variant mapping")
    spec_variant = spec_variants[0]
    _require_equal(spec_variant.get("variant_id"), variant_id, "strategy spec variant identity")
    _require_nonempty_string(spec_variant.get("title"), "strategy spec variant title")
    _require_equal(spec_variant.get("event_parameter_grid"), {}, "certified recipe event parameter grid")
    signature = _require_nonempty_string(spec_variant.get("mechanic_signature"), "strategy spec mechanic signature")
    structural = {
        spec_key: _binding_structure(ModuleBindingV1.model_validate(spec_variant[spec_key]), spec_key)
        for spec_key in ("entry", "stop", "target")
    }
    expected_signature = hashlib.sha256(
        json.dumps(structural, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    _require_equal(signature, expected_signature, "strategy spec mechanic signature")
    _require_equal(
        authoring.get("variant_mechanic_signatures"),
        {variant_id: signature},
        "authoring variant mechanic signatures",
    )
    distinctions = campaign.get("variant_distinctions")
    if not isinstance(distinctions, dict) or not isinstance(distinctions.get(variant_id), dict):
        raise ValueError("campaign variant distinctions are missing")
    _require_equal(
        distinctions[variant_id].get("mechanic_signature"),
        signature,
        "campaign variant mechanic signature",
    )
    _require_equal(
        (source_config.get("research_metadata") or {}).get("mechanic_signature"),
        signature,
        "source mechanic signature",
    )
    _require_equal(campaign.get("hypothesis"), strategy_spec.get("hypothesis"), "published hypothesis")
    rationales = spec_variant.get("rationales")
    if not isinstance(rationales, dict):
        raise ValueError("strategy spec variant rationales must be a mapping")
    source_research = source_config.get("research_metadata") or {}
    source_review = source_research.get("mechanics_review") or {}
    _require_equal(source_research.get("authoring_contract"), "alphaquest.campaign-draft/v1", "authoring contract")
    _require_equal(source_research.get("mechanics_review_version"), 1, "mechanics review version")
    _require_equal(source_review.get("pre_test_decision"), "approve_for_testing", "pre-test decision")
    rationale_bindings = {
        "mechanic": source_review.get("mechanic_expresses_edge"),
        "entry": source_review.get("entry_logic_rationale"),
        "stop": source_review.get("stop_loss_rationale"),
        "target": source_review.get("target_exit_rationale"),
        "timeframe_session": source_research.get("timeframe_rationale"),
    }
    _require_equal(rationales, rationale_bindings, "published variant rationales")
    _require_equal(distinctions[variant_id].get("mechanic"), rationales.get("mechanic"), "campaign mechanic rationale")
    _require_equal(
        source_review.get("profitability_rationale"),
        f"{strategy_spec.get('expected_mechanism')} {rationales.get('mechanic')}".strip(),
        "compiled profitability rationale",
    )
    _require_equal(
        source_review.get("known_failure_modes"),
        " ".join(strategy_spec.get("known_failure_modes") or []),
        "compiled known failure modes",
    )
    strategy = source_config.get("strategy") or {}
    for spec_key, config_key in (("entry", "entry"), ("stop", "sl"), ("target", "tp")):
        binding = spec_variant.get(spec_key)
        if not isinstance(binding, dict):
            raise ValueError(f"strategy spec variant {spec_key} must be a mapping")
        _require_equal(
            {key: binding.get(key) for key in ("module", "params")},
            {key: (strategy.get(config_key) or {}).get(key) for key in ("module", "params")},
            f"strategy spec {spec_key} binding",
        )
    declared_grid: dict[str, Any] = {}
    for spec_key, prefix in (("entry", "entry"), ("stop", "sl"), ("target", "tp")):
        grid = spec_variant[spec_key].get("parameter_grid") or {}
        if not isinstance(grid, dict):
            raise ValueError(f"strategy spec variant {spec_key} parameter_grid must be a mapping")
        declared_grid.update({f"{prefix}.params.{name}": value for name, value in grid.items()})
    _require_equal((source_config.get("core_grid") or {}).get("parameters") or {}, declared_grid, "authoring core grid")
    _require_equal((source_config.get("wfa") or {}).get("parameters") or {}, declared_grid, "authoring WFA grid")
    return {
        "manifest": _artifact(manifest_path, project_root=project_root),
        "authoring_lane": "certified_recipe",
        "certified_recipe": recipe,
        "variant_id": variant_id,
        "mechanic_signature": signature,
        "execution": execution,
        "documents": documents,
        "_campaign_document": campaign,
        "_campaign_artifact": next(item for item in documents if item["path"].endswith("campaign.yaml")),
    }


def _preflight_binding(
    receipt_path: Path,
    source_path: Path,
    embedded: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    receipt = _read_json(receipt_path, "pre-run preflight receipt")
    _require_equal(receipt, embedded, "separate pre-run preflight receipt")
    if receipt.get("passed") is not True or receipt.get("failures"):
        raise ValueError("pre-run configuration/data preflight must pass without failures")
    _require_equal(receipt.get("tests_ran"), False, "pre-run preflight tests_ran")
    _require_equal(receipt.get("include_generated_results"), False, "pre-run preflight generated-results flag")
    _require_equal(receipt.get("data_sources_checked"), 1, "pre-run preflight data source count")
    _require_equal(receipt.get("data_cache_hits"), 0, "pre-run preflight data cache hits")
    _require_equal(receipt.get("terminal_configs_not_executed"), 0, "pre-run preflight terminal config count")
    _require_equal(
        _normalized_paths(receipt.get("configs_checked"), project_root, "pre-run preflight configs_checked"),
        [source_path.resolve()],
        "pre-run preflight config identity",
    )
    current = run_preflight(config_paths=[source_path], run_tests=False, project_root=project_root)
    if current.get("passed") is not True or current.get("failures"):
        raise ValueError("current authored config/data preflight failed")
    _require_equal(current.get("tests_ran"), False, "current config validation tests_ran")
    _require_equal(
        _normalized_paths(current.get("configs_checked"), project_root, "current preflight configs_checked"),
        [source_path.resolve()],
        "current preflight config identity",
    )
    for field in (
        "passed",
        "failures",
        "warnings",
        "tests_ran",
        "include_generated_results",
        "data_sources_checked",
        "data_cache_hits",
        "terminal_configs_not_executed",
    ):
        _require_equal(current.get(field), receipt.get(field), f"current/recorded preflight {field}")
    return {
        "recorded_receipt": _artifact(receipt_path, project_root=project_root),
        "recorded": receipt,
        "current_config_validation": current,
        "repository_engineering_tests_verified": False,
    }


def _timeframe_minutes(value: Any) -> float:
    text = _require_nonempty_string(value, "mechanics metadata timeframe")
    unit = text[-1]
    try:
        amount = float(text[:-1])
    except ValueError as exc:
        raise ValueError("mechanics metadata timeframe is invalid") from exc
    multiplier = {"m": 1.0, "h": 60.0, "d": 1440.0}.get(unit)
    if multiplier is None or amount <= 0:
        raise ValueError("mechanics metadata timeframe is invalid")
    return amount * multiplier


def _mechanics_evidence_contract(
    *,
    source_config: dict[str, Any],
    evidence_dir: Path,
    technical_gate: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    metadata = _read_json(evidence_dir / "metadata.json", "mechanics evidence metadata")
    _require_equal(metadata.get("artifact_files"), _MECHANICS_ARTIFACT_FILES, "mechanics artifact map")
    counts = metadata.get("record_counts")
    if not isinstance(counts, dict):
        raise ValueError("mechanics metadata record_counts must be a mapping")
    _require_equal(set(counts), set(_MECHANICS_ARTIFACT_FILES), "mechanics record-count identities")
    observed_counts: dict[str, int] = {}
    for artifact_id, filename in _MECHANICS_ARTIFACT_FILES.items():
        path = evidence_dir / filename
        if not path.is_file():
            raise ValueError(f"mechanics declared artifact is missing: {filename}")
        try:
            observed = int(pq.ParquetFile(path).metadata.num_rows)
        except (OSError, ValueError) as exc:
            raise ValueError(f"mechanics declared artifact could not be read: {filename}: {exc}") from exc
        value = counts.get(artifact_id)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"mechanics record count must be a non-negative integer: {artifact_id}")
        _require_equal(value, observed, f"mechanics record count {artifact_id}")
        observed_counts[artifact_id] = observed

    data = source_config.get("data") or {}
    core = source_config.get("core") or {}
    apex = source_config.get("apex_rules") or {}
    execution = ExecutionAssumptions.from_core_config(core)
    expected = {
        "campaign_id": source_config.get("campaign_id"),
        "strategy_id": source_config.get("strategy_name"),
        "variant_id": source_config.get("variant_id"),
        "symbol": source_config.get("symbol") or data.get("symbol"),
        "stage": "core",
        "timezone": data.get("exchange_timezone"),
        "tick_size": execution.tick_size,
        "tick_value": execution.tick_value,
        "timeframe": source_config.get("timeframe") or data.get("source_timeframe"),
        "timeframe_minutes": _timeframe_minutes(source_config.get("timeframe") or data.get("source_timeframe")),
        "config_hash": technical_gate.get("config_hash"),
        "input_data_hash": technical_gate.get("input_data_hash"),
        "strategy_implementation_version": technical_gate.get("strategy_implementation_version"),
        "strategy_implementation_sha256": technical_gate.get("strategy_implementation_sha256"),
        "strategy_certification_manifest_sha256": technical_gate.get("strategy_certification_manifest_sha256"),
        "validation_lane": technical_gate.get("lane"),
        "source_data_type": data.get("source"),
        "source_trade_count": observed_counts["trades"],
        "commission_per_contract": execution.commission_per_contract,
        "slippage_ticks": execution.slippage_ticks,
        "point_value": execution.point_value,
        "forced_flatten_time": apex.get("force_flatten_time"),
        "schema_version": technical_gate.get("validation_schema_version"),
    }
    for field, value in expected.items():
        _require_equal(metadata.get(field), value, f"mechanics metadata {field}")
    _require_nonempty_string(metadata.get("run_id"), "mechanics metadata run_id")
    _require_nonempty_string(metadata.get("notes"), "mechanics metadata notes")
    reviewed_at = _require_nonempty_string(metadata.get("created_at_utc"), "mechanics metadata created_at_utc")
    try:
        timestamp = datetime.fromisoformat(reviewed_at)
    except ValueError as exc:
        raise ValueError("mechanics metadata created_at_utc must be an ISO timestamp") from exc
    if timestamp.utcoffset() is None:
        raise ValueError("mechanics metadata created_at_utc must be timezone-aware")
    gate = (source_config.get("research_metadata") or {}).get("validation_gate") or {}
    requested_samples = gate.get("manual_review_random_sample_size")
    declared_minimum_samples = gate.get("minimum_trade_samples")
    minimum_samples = metadata.get("minimum_trade_samples")
    if isinstance(minimum_samples, bool) or not isinstance(minimum_samples, int) or minimum_samples < 1:
        raise ValueError("mechanics metadata minimum_trade_samples must be a positive integer")
    _require_equal(minimum_samples, declared_minimum_samples, "mechanics metadata minimum trade samples")
    if (
        isinstance(requested_samples, bool)
        or not isinstance(requested_samples, int)
        or minimum_samples < requested_samples
    ):
        raise ValueError("mechanics minimum trade samples cannot be below the manual sample size")
    source_value = data.get("raw_csv" if data.get("source") == "csv" else "raw_parquet")
    _require_equal(
        _resolve_reference(metadata.get("source_data_path"), project_root, "mechanics metadata source_data_path"),
        _resolve_reference(source_value, project_root, "configured mechanics source data"),
        "mechanics metadata source data path",
    )
    return {
        "metadata": metadata,
        "observed_record_counts": observed_counts,
    }


def _mechanics_bindings(
    source_config: dict[str, Any],
    source_path: Path,
    summary: dict[str, Any],
    manifest: dict[str, Any],
    project_root: Path,
    canonical_input_hash: str,
) -> dict[str, Any]:
    summary_gate = summary.get("mechanics_validation_gate")
    manifest_gate = manifest.get("mechanics_validation_gate")
    if not isinstance(summary_gate, dict) or not isinstance(manifest_gate, dict):
        raise ValueError("run does not record a mechanics validation gate")
    _require_equal(manifest_gate, summary_gate, "manifest mechanics gate")
    _require_equal(summary_gate.get("status"), "APPROVED_FOR_TESTING", "mechanics gate status")
    _require_equal(summary_gate.get("verdict"), "PASS", "mechanics gate verdict")
    _require_equal(summary_gate.get("required"), True, "mechanics gate required flag")
    _require_equal(summary_gate.get("approval_status"), "approved_for_testing", "mechanics approval status")
    if summary_gate.get("errors"):
        raise ValueError("mechanics gate records errors")

    research = source_config.get("research_metadata")
    gate = research.get("validation_gate") if isinstance(research, dict) else None
    if not isinstance(gate, dict) or gate.get("required") is not True:
        raise ValueError("source config lacks a required mechanics validation gate")
    lane = _require_nonempty_string(gate.get("lane"), "source mechanics validation lane").lower()
    _require_equal(summary_gate.get("lane"), lane, "mechanics gate lane")
    _require_equal(
        _resolve_reference(summary_gate.get("config_path"), project_root, "recorded mechanics config_path"),
        source_path.resolve(),
        "mechanics gate config path",
    )
    _require_equal(summary_gate.get("config_hash"), summary.get("source_config_hash"), "mechanics gate config hash")
    evidence_dir = _resolve_reference(gate.get("evidence_dir"), project_root, "mechanics evidence_dir")
    approval_path = _resolve_reference(gate.get("approval_path"), project_root, "mechanics approval_path")
    _require_equal(
        _resolve_reference(summary_gate.get("evidence_dir"), project_root, "recorded mechanics evidence_dir"),
        evidence_dir,
        "mechanics evidence path",
    )
    _require_equal(
        _resolve_reference(summary_gate.get("approval_path"), project_root, "recorded mechanics approval_path"),
        approval_path,
        "mechanics approval path",
    )
    if not evidence_dir.is_dir():
        raise ValueError(f"mechanics evidence directory is missing: {evidence_dir}")
    evidence_files = sorted(path for path in evidence_dir.iterdir() if path.is_file())
    if not evidence_files:
        raise ValueError(f"mechanics evidence directory contains no files: {evidence_dir}")
    technical_gate = inspect_validation_gate(
        source_config,
        source_path,
        precomputed_input_hash=canonical_input_hash,
    )
    if technical_gate.get("errors"):
        raise ValueError("current mechanics technical inspection failed: " + "; ".join(technical_gate["errors"]))
    _require_equal(set(technical_gate), set(summary_gate), "recorded/current mechanics gate fields")
    for field in ("config_path", "evidence_dir", "approval_path"):
        _require_equal(
            _resolve_reference(technical_gate.get(field), project_root, f"current mechanics {field}"),
            _resolve_reference(summary_gate.get(field), project_root, f"recorded mechanics {field}"),
            f"recorded/current mechanics {field}",
        )
    for field in set(technical_gate) - {"config_path", "evidence_dir", "approval_path"}:
        _require_equal(technical_gate.get(field), summary_gate.get(field), f"recorded/current mechanics {field}")
    evidence_contract = _mechanics_evidence_contract(
        source_config=source_config,
        evidence_dir=evidence_dir,
        technical_gate=technical_gate,
        project_root=project_root,
    )
    approval = _read_json(approval_path, "mechanics approval")
    _require_equal(approval.get("schema"), APPROVAL_SCHEMA, "mechanics approval schema")
    _require_equal(
        approval.get("review_scope"),
        "implementation_matches_frozen_specification",
        "mechanics approval review scope",
    )
    _require_equal(approval.get("profitability_approval"), False, "mechanics profitability approval")
    _require_equal(approval.get("config_hash"), summary.get("source_config_hash"), "mechanics approval config hash")
    _require_equal(
        approval.get("input_data_hash"), summary_gate.get("input_data_hash"), "mechanics approval input hash"
    )
    for approval_field, gate_field in (
        ("status", "approval_status"),
        ("reviewer", "reviewer"),
        ("reviewed_at", "reviewed_at"),
        ("lane", "lane"),
        ("validation_schema_version", "validation_schema_version"),
        ("strategy_implementation_version", "strategy_implementation_version"),
        ("strategy_implementation_sha256", "strategy_implementation_sha256"),
        ("strategy_certification_manifest_sha256", "strategy_certification_manifest_sha256"),
    ):
        if approval_field in approval or summary_gate.get(gate_field) is not None:
            _require_equal(
                approval.get(approval_field),
                summary_gate.get(gate_field),
                f"mechanics approval {approval_field}",
            )
    _require_nonempty_string(approval.get("reviewer"), "mechanics approval reviewer")
    _require_nonempty_string(approval.get("reviewed_at"), "mechanics approval reviewed_at")
    for approval_field, gate_field in (
        ("fixed_random_sample_size", "manual_review_random_sample_size"),
        ("fixed_random_seed", "manual_review_seed"),
        ("parameter_mode", "parameter_mode"),
    ):
        if gate.get(gate_field) is not None:
            _require_equal(approval.get(approval_field), gate.get(gate_field), f"mechanics approval {approval_field}")
    _validate_approval_sampling(approval, evidence_dir)
    plan = MechanicsApprovalService().plan(source_path)
    plan_document = plan.model_dump(mode="json")
    _require_equal(plan_document.get("config_path"), str(source_path.resolve()), "mechanics planner config path")
    if plan.blockers:
        raise ValueError("mechanics planner records blockers: " + "; ".join(plan.blockers))
    if plan.unreviewed_trade_ids:
        raise ValueError("mechanics planner records unreviewed sampled trades")
    if plan.non_correct_trade_ids:
        raise ValueError("mechanics planner records non-Correct sampled trades")
    for field in (
        "lane",
        "config_hash",
        "input_data_hash",
        "validation_schema_version",
        "strategy_implementation_version",
        "strategy_implementation_sha256",
        "strategy_certification_manifest_sha256",
        "fixed_random_sample_size",
        "fixed_random_seed",
        "sampling_policy_version",
        "sampling_policy_sha256",
        "sampled_trade_ids",
        "sampling_categories",
        "sampling_reasons",
    ):
        _require_equal(approval.get(field), plan_document.get(field), f"mechanics approval/planner {field}")

    reviews = load_manual_reviews(evidence_dir)
    sampled_keys = [_trade_id_key(value, "sampled_trade_ids") for value in plan.sampled_trade_ids]
    review_rows: dict[str, list[dict[str, Any]]] = {key: [] for key in sampled_keys}
    for row in reviews.to_dict("records"):
        key = trade_id_key(row.get("trade_id"))
        if key in review_rows:
            review_rows[key].append(row)
    for key in sampled_keys:
        rows = review_rows[key]
        _require_equal(len(rows), 1, f"mechanics sampled trade {key} review count")
        _require_equal(
            str(rows[0].get("reviewer_status") or "").casefold(), "correct", f"mechanics sampled trade {key} status"
        )
        _require_nonempty_string(rows[0].get("reviewer_notes"), f"mechanics sampled trade {key} notes")
    return {
        "recorded_gate": deepcopy(summary_gate),
        "gate_currently_revalidated": False,
        "human_authority_verified": False,
        "evidence_inventory_only": False,
        "technical_gate_inspector_validated": True,
        "technical_gate_report": technical_gate,
        "retained_evidence_contract": evidence_contract,
        "planner_contract_validated": True,
        "planner": plan_document,
        "approval_record": {
            key: approval.get(key)
            for key in (
                "schema",
                "status",
                "reviewer",
                "reviewed_at",
                "notes",
                "config_hash",
                "input_data_hash",
                "lane",
                "validation_schema_version",
                "fixed_random_sample_size",
                "fixed_random_seed",
                "parameter_mode",
                "review_scope",
                "profitability_approval",
                "sampled_trade_ids",
                "sampling_categories",
                "sampling_reasons",
                "sampling_policy_version",
                "sampling_policy_sha256",
            )
        },
        "approval": _artifact(approval_path, project_root=project_root),
        "evidence": [_artifact(path, project_root=project_root) for path in evidence_files],
    }


def _dataset_binding(source_config: dict[str, Any], summary: dict[str, Any], project_root: Path) -> dict[str, Any]:
    data = source_config.get("data")
    if not isinstance(data, dict):
        raise ValueError("source config data section is missing")
    dataset_id = str(data.get("dataset_id") or "")
    _require_equal(dataset_id, summary.get("dataset_id"), "dataset identity")
    layout = load_storage_layout(project_root)
    manifest_path = layout.dataset_root / dataset_id / "dataset_manifest.json"
    dataset_manifest = _read_json(manifest_path, "dataset manifest")
    try:
        DatasetManifestV1.model_validate(dataset_manifest)
    except ValueError as exc:
        raise ValueError(f"dataset manifest contract failed: {exc}") from exc
    _require_equal(dataset_manifest.get("dataset_id"), dataset_id, "dataset manifest identity")
    _require_equal(dataset_manifest.get("quality_verdict"), "PASS", "dataset quality verdict")
    source = str(data.get("source") or "").strip().lower()
    if source not in {"csv", "parquet"}:
        raise ValueError(
            "MVP diagnostic indexing supports one local CSV or Parquet bar dataset; "
            f"unsupported source {source!r} requires a separate binding design"
        )
    _require_equal(str(dataset_manifest.get("source") or "").strip().lower(), source, "dataset source")
    execution_fields = {
        "symbol": source_config.get("symbol") or data.get("symbol"),
        "timeframe": source_config.get("timeframe") or data.get("source_timeframe"),
        "timezone": data.get("source_timezone"),
        "exchange_timezone": data.get("exchange_timezone"),
        "timestamp_semantics": data.get("timestamp_semantics"),
        "source_timestamp_semantics": data.get("source_timestamp_semantics"),
        "source_sha256": data.get("source_sha256"),
        "canonical_sha256": data.get("canonical_sha256"),
        "coverage_start": data.get("coverage_start"),
        "coverage_end": data.get("coverage_end"),
        "roll_policy": data.get("roll_policy"),
        "continuous_contract": data.get("continuous_contract"),
        "contract_column": data.get("contract_column"),
        "contract_count": data.get("contract_count"),
        "roll_calendar": data.get("roll_calendar"),
        "roll_calendar_sha256": data.get("roll_calendar_sha256"),
        "certified_features": data.get("certified_features"),
    }
    required_execution_fields = {
        "symbol",
        "timeframe",
        "timezone",
        "exchange_timezone",
        "timestamp_semantics",
        "source_timestamp_semantics",
        "source_sha256",
        "canonical_sha256",
        "coverage_start",
        "coverage_end",
        "roll_policy",
        "continuous_contract",
        "contract_count",
        "certified_features",
    }
    missing = sorted(field for field in required_execution_fields if execution_fields[field] is None)
    if missing:
        raise ValueError(f"source config lacks dataset execution metadata: {', '.join(missing)}")
    for field, expected in execution_fields.items():
        if expected is not None or field in required_execution_fields:
            _require_equal(dataset_manifest.get(field), expected, f"dataset manifest {field}")
    _require_equal(data.get("timezone"), data.get("exchange_timezone"), "engine/exchange timezone")
    _require_equal(dataset_manifest.get("symbol"), summary.get("symbol"), "dataset/run symbol")
    _require_equal(dataset_manifest.get("timeframe"), summary.get("timeframe"), "dataset/run timeframe")
    canonical_path = _resolve_reference(dataset_manifest.get("path"), project_root, "canonical dataset")
    configured_path = _resolve_reference(
        data.get("raw_csv" if source == "csv" else "raw_parquet"),
        project_root,
        f"configured {source} dataset",
    )
    _require_equal(configured_path, canonical_path, "configured canonical dataset path")
    canonical = _artifact(canonical_path, project_root=project_root)
    _require_equal(canonical["sha256"], dataset_manifest.get("canonical_sha256"), "dataset manifest canonical hash")
    _require_equal(canonical["sha256"], data.get("canonical_sha256"), "source config canonical hash")
    gate = summary["mechanics_validation_gate"]
    _require_equal(canonical["sha256"], gate.get("input_data_hash"), "mechanics input data hash")
    return {
        "dataset_id": dataset_id,
        "manifest": _artifact(manifest_path, project_root=project_root),
        "manifest_document": dataset_manifest,
        "manifest_historical_run_hash_recorded": False,
        "binding_scope": (
            "Current manifest bytes are validated against frozen config and published strategy-spec metadata; "
            "the staged run did not record a historical dataset-manifest file hash."
        ),
        "canonical_file": canonical,
    }


def _derive_diagnostic_classification(
    *,
    source_config: dict[str, Any],
    source_artifact: dict[str, Any],
    campaign: dict[str, Any],
    campaign_artifact: dict[str, Any],
    mechanics: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    disclosures: list[dict[str, Any]] = []
    source_synthetic = False
    mechanics_simulated = False
    scripted_admission = False
    terms = ("synthetic", "simulated", "fixture", "no owner authority")

    def record(artifact: dict[str, Any], field: str, value: Any, disclosure: str) -> bool:
        if not isinstance(value, str) or not any(term in value.casefold() for term in terms):
            return False
        disclosures.append(
            {
                "artifact_path": artifact["path"],
                "artifact_sha256": artifact.get("sha256") or artifact.get("file_sha256"),
                "field": field,
                "disclosure": disclosure,
                "observed_value": value,
            }
        )
        return True

    for field in ("title", "edge_family"):
        source_synthetic |= record(
            campaign_artifact, f"campaign.{field}", campaign.get(field), "authored_synthetic_context"
        )
    sources = campaign.get("sources")
    if isinstance(sources, list):
        for index, item in enumerate(sources):
            if isinstance(item, dict):
                for field in ("title", "link", "relevance"):
                    source_synthetic |= record(
                        campaign_artifact,
                        f"campaign.sources[{index}].{field}",
                        item.get(field),
                        "authored_synthetic_context",
                    )
    duplicate = campaign.get("duplicate_edge_review")
    if isinstance(duplicate, dict):
        value = duplicate.get("substantive_distinction")
        source_synthetic |= record(
            campaign_artifact,
            "campaign.duplicate_edge_review.substantive_distinction",
            value,
            "authored_synthetic_context",
        )
        scripted_admission |= isinstance(value, str) and any(
            term in value.casefold() for term in ("scripted", "admission")
        )
    for owner, artifact, objectives in (
        ("campaign", campaign_artifact, campaign.get("research_objectives")),
        ("source_config", source_artifact, source_config.get("research_objectives")),
    ):
        if isinstance(objectives, dict):
            source_synthetic |= record(
                artifact,
                f"{owner}.research_objectives.development_goal",
                objectives.get("development_goal"),
                "authored_synthetic_context",
            )
            retirement = objectives.get("retirement_rules")
            if isinstance(retirement, list):
                for index, value in enumerate(retirement):
                    source_synthetic |= record(
                        artifact,
                        f"{owner}.research_objectives.retirement_rules[{index}]",
                        value,
                        "authored_synthetic_context",
                    )
    dataset_id = (source_config.get("data") or {}).get("dataset_id") or source_config.get("dataset_id")
    source_synthetic |= record(source_artifact, "source_config.dataset_id", dataset_id, "authored_synthetic_context")
    if (source_config.get("campaign_id"), dataset_id) == (
        "tutorial_calendar_bias",
        "synthetic_tutorial_es_1m",
    ):
        disclosures.append(
            {
                "artifact_path": source_artifact["path"],
                "artifact_sha256": source_artifact["sha256"],
                "field": "source_config.campaign_id+dataset_id",
                "disclosure": "established_tutorial_fixture_identity",
                "observed_value": [source_config.get("campaign_id"), dataset_id],
            }
        )
        source_synthetic = True

    approval = mechanics["approval_record"]
    approval_artifact = mechanics["approval"]
    reviewer = approval.get("reviewer")
    notes = approval.get("notes")
    if reviewer == "SIMULATED_MVP_FIXTURE_ONLY":
        record(approval_artifact, "approval.reviewer", reviewer, "simulated_mechanics_context")
        mechanics_simulated = True
    if record(approval_artifact, "approval.notes", notes, "mechanics_context_disclosure"):
        source_synthetic |= isinstance(notes, str) and any(
            term in notes.casefold() for term in ("synthetic", "fixture")
        )
        mechanics_simulated |= isinstance(notes, str) and any(
            term in notes.casefold() for term in ("simulated", "no owner authority")
        )

    explicit = bool(disclosures)
    classification = "SYNTHETIC_OR_SIMULATED_CONTEXT" if explicit else "UNVERIFIED_ORIGIN"
    limitations = [
        "This classification preserves explicit structured disclosures; it does not independently verify origin.",
        "No universal historical origin field or verified-origin assurance is available to this report.",
    ]
    if not explicit:
        limitations.append("No positive real-origin classification is supported.")
    result = {
        "classification": classification,
        "classification_kind": "CONSERVATIVE_DIAGNOSTIC_WARNING",
        "verified_origin_assertion": False,
        "data_origin_verified": False,
        "source_review_verified": False,
        "implementation_admission_verified": False,
        "human_mechanics_authority_verified": False,
        "source_synthetic_disclosed": source_synthetic,
        "mechanics_simulated_disclosed": mechanics_simulated,
        "synthetic_or_simulated_disclosures": disclosures,
        "conflicts": [],
        "limitations": limitations,
    }
    if explicit:
        labels = [
            "Bound inputs explicitly disclose synthetic or simulated context; this is a diagnostic warning, not independently verified origin."
        ]
        if source_synthetic:
            labels.append("Synthetic fixture source; not independently verified.")
        if scripted_admission:
            labels.append("Duplicate and implementation-admission decisions are scripted fixture context.")
        if mechanics_simulated:
            labels.append("Mechanics approval is simulated and has no owner authority.")
        labels.extend(
            [
                "Operational PASS means only that the harness produced bound diagnostic evidence.",
                "MVP overall NEEDS MANUAL REVIEW.",
            ]
        )
    else:
        labels = [
            "User-supplied diagnostic evidence of unverified data origin.",
            "No real-data provenance classification is made by this index.",
            "Recorded mechanics approval is reported, not independently re-audited by this index.",
            "MVP overall NEEDS MANUAL REVIEW.",
        ]
    return result, labels


def _bind_run_manifest(
    run_dir: Path,
    source_path: Path,
    source_config: dict[str, Any],
    effective_config: dict[str, Any],
    summary: dict[str, Any],
    manifest: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    _require_equal(summary.get("halted"), False, "diagnostic halted flag")
    data = effective_config.get("data") or {}
    expected_source = str(data.get("source") or "").strip() or (
        "databento_dbn"
        if data.get("raw_dir")
        else "parquet"
        if data.get("raw_parquet")
        else "csv"
        if data.get("raw_csv")
        else None
    )
    expected_data = {
        "data_source": expected_source,
        "raw_csv": str(data.get("raw_csv")) if data.get("raw_csv") else None,
        "raw_parquet": str(data.get("raw_parquet")) if data.get("raw_parquet") else None,
        "raw_dir": str(data.get("raw_dir")) if data.get("raw_dir") else None,
    }
    for field, expected in expected_data.items():
        _require_equal(summary.get(field), expected, f"summary {field}")
    _require_equal(summary.get("research_policy"), effective_config.get("research_policy"), "summary research policy")
    _require_equal(summary.get("engine_contract_version"), ENGINE_CONTRACT_VERSION, "summary engine contract")
    created_at = _require_nonempty_string(summary.get("created_at"), "summary created_at")
    _require_equal(summary.get("updated_at"), created_at, "summary producer timestamp")
    _require_aware_datetime(created_at, "summary created_at")
    for field in (
        *_IDENTITY_FIELDS,
        "timeframe",
        "data_source",
        "raw_csv",
        "raw_parquet",
        "raw_dir",
        "campaign_metadata",
        "variant_metadata",
        "research_policy",
        "engine_contract_version",
        "config_hash",
        "source_config_hash",
        "created_at",
        "updated_at",
        "mechanics_validation_gate",
        "submission_preflight",
        "diagnostic_only",
        "diagnostic_reasons",
        "authoritative_parallel_workers",
        "authoritative_core_grid_workers",
        "research_verdict",
        "generic_objective_verdict",
        "scientific_validity_verdict",
    ):
        _require_equal(manifest.get(field), summary.get(field), f"manifest {field}")
    _require_equal(manifest.get("layout"), "campaign_variant_symbol_run", "manifest layout")
    _require_equal(manifest.get("stage_order"), PRE_ACCEPTANCE_STAGE_ORDER, "manifest stage order")
    variant_metadata = summary.get("variant_metadata")
    if not isinstance(variant_metadata, dict):
        raise ValueError("summary variant_metadata must be a mapping")
    variant_path = _resolve_reference(variant_metadata.get("path"), project_root, "variant metadata")
    variant_artifact = _artifact(variant_path, project_root=project_root)
    _require_equal(variant_artifact["sha256"], variant_metadata.get("hash"), "variant metadata hash")
    variant_document = _read_yaml(variant_path, "variant metadata")
    _require_equal(variant_document.get("campaign_id"), source_config.get("campaign_id"), "variant metadata campaign")
    _require_equal(variant_document.get("variant_id"), source_config.get("variant_id"), "variant metadata variant")
    mechanic = strategy_mechanic(effective_config)
    _require_equal(variant_metadata.get("mechanic"), mechanic, "summary variant mechanic")
    _require_equal(variant_document.get("mechanic"), mechanic, "variant metadata mechanic")
    campaign_artifact = None
    campaign_metadata = summary.get("campaign_metadata")
    if campaign_metadata is not None:
        if not isinstance(campaign_metadata, dict):
            raise ValueError("summary campaign_metadata must be null or a mapping")
        campaign_path = _resolve_reference(campaign_metadata.get("path"), project_root, "campaign metadata")
        campaign_artifact = _artifact(campaign_path, project_root=project_root)
        _require_equal(campaign_artifact["sha256"], campaign_metadata.get("hash"), "campaign metadata hash")
        campaign_document = _read_yaml(campaign_path, "campaign metadata")
        _require_equal(
            campaign_document.get("campaign_id"), source_config.get("campaign_id"), "campaign metadata identity"
        )
    results_value = summary.get("source_results_index_path")
    manifest_results = manifest.get("source_results_index")
    if results_value is None or manifest_results is None:
        raise ValueError("run producer did not record the source results index")
    results_path = _resolve_reference(results_value, project_root, "summary source results index")
    _require_equal(
        _resolve_reference(manifest_results, project_root, "manifest source results index"),
        results_path,
        "source results index path",
    )
    context = resolve_campaign_context(source_path, project_root=project_root)
    if context is None:
        raise ValueError("authored source config has no campaign context")
    _require_equal(results_path, context.results_index.resolve(), "canonical source results index path")
    results = _read_yaml(results_path, "source results index")
    _require_equal(results.get("campaign_id"), source_config.get("campaign_id"), "source results index campaign")
    _require_equal(results.get("generated_by"), "alphaquest.run_campaign_stages", "source results index producer")
    _require_equal(
        results.get("description"),
        "Navigation pointers from authored source configs to generated backtest evidence.",
        "source results index description",
    )
    entries = results.get("runs")
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        raise ValueError("source results index runs must be a list of mappings")
    expected_entry = {
        "campaign_id": summary.get("campaign_id"),
        "variant_id": summary.get("variant_id"),
        "symbol": summary.get("symbol"),
        "test_run_id": summary.get("test_run_id"),
        "attempt_id": summary.get("attempt_id"),
        "attempt_kind": summary.get("attempt_kind"),
        "attempt_provenance": summary.get("attempt_provenance"),
        "parent_attempt_id": summary.get("parent_attempt_id"),
        "source_config_path": summary.get("source_config_path"),
        "source_config_snapshot_path": summary.get("source_config_snapshot_path"),
        "source_config_hash": summary.get("source_config_hash"),
        "effective_config_path": summary.get("effective_config_path"),
        "effective_config_hash": summary.get("config_hash"),
        "run_dir": str(Path(str(summary.get("output_dir")))),
        "campaign_test_summary": str(Path(str(summary.get("output_dir"))) / "campaign_test_summary.json"),
        "variant_test_summary": str(Path(str(summary.get("output_dir"))) / "variant_test_summary.json"),
        "passed": summary.get("passed"),
        "research_verdict": summary.get("research_verdict"),
        "finalization_state": summary.get("finalization_state"),
        "result_bundle_path": summary.get("result_bundle_path"),
        "incomplete_attempt_marker_path": summary.get("incomplete_attempt_marker_path"),
        "diagnostic_only": summary.get("diagnostic_only"),
        "halted": summary.get("halted"),
        "failed_stage": _first_failed_stage(summary.get("stages") or []),
        "updated_at": summary.get("updated_at"),
    }
    matches = [entry for entry in entries if entry == expected_entry]
    _require_equal(len(matches), 1, "source results index exact run entry count")
    _require_equal(
        _resolve_reference(matches[0].get("source_config_path"), project_root, "results index source config"),
        source_path,
        "source results index source config identity",
    )
    return {
        "campaign_metadata": campaign_artifact,
        "variant_metadata": variant_artifact,
        "source_results_index": _artifact(results_path, project_root=project_root),
        "source_results_index_entry": deepcopy(expected_entry),
    }


def _data_quality_projection(stage_dir: Path, observed: Any) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(observed, dict):
        raise ValueError(f"{stage_dir.name} data_quality must be a mapping")
    report_path = stage_dir / "validation" / "data_quality_report.csv"
    if not report_path.is_file():
        raise ValueError(f"missing retained data-quality report: {report_path}")
    with report_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    _require_equal(len(rows), 1, f"{stage_dir.name} data-quality row count")
    retained = rows[0]
    expected_keys = set(retained) | _UNVERIFIED_DATA_QUALITY_FIELDS
    _require_equal(set(observed), expected_keys, f"{stage_dir.name} data-quality fields")
    for field, expected in retained.items():
        _require_equal(str(observed.get(field)), expected, f"{stage_dir.name} retained data quality {field}")
    duration = observed.get("prepare_data_duration_seconds")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration < 0:
        raise ValueError(f"{stage_dir.name} prepare_data_duration_seconds must be non-negative")
    if not isinstance(observed.get("prepared_data_cache"), dict):
        raise ValueError(f"{stage_dir.name} prepared_data_cache must be a mapping")
    return ({field: observed[field] for field in retained}, sorted(_UNVERIFIED_DATA_QUALITY_FIELDS))


def _execution_assumption_records(value: Any, location: str = "$") -> list[tuple[str, Any]]:
    records: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_location = f"{location}.{key}"
            if key == "execution_assumptions":
                records.append((child_location, child))
            records.extend(_execution_assumption_records(child, child_location))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            records.extend(_execution_assumption_records(child, f"{location}[{index}]"))
    return records


def _validate_execution_assumptions(
    stage: str,
    canonical_summary: dict[str, Any],
    artifact_paths: list[Path],
    expected: dict[str, Any],
) -> None:
    found: list[str] = []
    for location, value in _execution_assumption_records(canonical_summary, "canonical_summary"):
        _require_equal(value, expected, f"{stage} {location}")
        found.append(location)
    for path in artifact_paths:
        if path.suffix.lower() != ".json":
            continue
        document = _read_json(path, f"{stage} JSON artifact")
        for location, value in _execution_assumption_records(document, path.name):
            _require_equal(value, expected, f"{stage} {location}")
            found.append(location)
    if stage == "limited_core_grid_test":
        required = {
            "canonical_summary.fixed_config_core.reproducibility.execution_assumptions",
            "fixed_config_core_metrics.json.reproducibility.execution_assumptions",
        }
        if not required.issubset(found):
            raise ValueError(f"{stage} lacks required execution-assumption evidence: {sorted(required - set(found))}")


def _engine_config_hash_records(value: Any, location: str = "$") -> list[tuple[str, Any]]:
    records: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_location = f"{location}.{key}"
            if key == "reproducibility" and isinstance(child, dict) and "config_hash" in child:
                records.append((f"{child_location}.config_hash", child.get("config_hash")))
            records.extend(_engine_config_hash_records(child, child_location))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            records.extend(_engine_config_hash_records(child, f"{location}[{index}]"))
    return records


def _validate_engine_config_hashes(
    stage: str,
    canonical_summary: dict[str, Any],
    artifact_paths: list[Path],
    effective_config: dict[str, Any],
) -> list[dict[str, str]]:
    expected = object_sha256(effective_config)
    records = _engine_config_hash_records(canonical_summary, "canonical_summary")
    for path in artifact_paths:
        if path.suffix.lower() == ".json":
            records.extend(
                _engine_config_hash_records(
                    _read_json(path, f"{stage} JSON artifact"),
                    path.name,
                )
            )
    bound: list[dict[str, str]] = []
    for location, value in records:
        is_fixed_replay = stage == "limited_core_grid_test" and (
            ".fixed_config_core.reproducibility.config_hash" in location
            or location == "fixed_config_core_metrics.json.reproducibility.config_hash"
        )
        if not is_fixed_replay:
            raise ValueError(f"{stage} contains an engine config hash for an unbound transformed execution: {location}")
        _require_equal(value, expected, f"{stage} {location}")
        bound.append({"location": location, "config_hash": expected})
    return bound


def _validate_selected_params(
    selected: Any,
    parameters: Any,
    label: str,
    *,
    require_complete: bool = False,
) -> dict[str, Any]:
    if not isinstance(selected, dict):
        raise ValueError(f"{label} must be a mapping")
    if not selected:
        if require_complete and parameters:
            raise ValueError(f"{label} must contain the complete frozen parameter selection")
        return {}
    if not isinstance(parameters, dict):
        raise ValueError(f"{label} frozen parameters must be a mapping")
    _require_equal(set(selected), set(parameters), f"{label} identities")
    for name, value in selected.items():
        values = parameters.get(name)
        if not isinstance(values, list) or value not in values:
            raise ValueError(f"{label} value is outside the frozen grid: {name}")
    return deepcopy(selected)


def _published_parameter_grid(
    effective_config: dict[str, Any],
    section: str,
    stage_cfg: dict[str, Any],
) -> dict[str, Any]:
    section_config = effective_config.get(section) or {}
    parameters = section_config.get("parameters") or {}
    if not isinstance(parameters, dict):
        raise ValueError(f"published {section} parameters must be a mapping")
    if "parameters" in stage_cfg and stage_cfg.get("parameters") != parameters:
        raise ValueError(f"{section} stage-local parameters diverge from the published grid")
    return deepcopy(parameters)


def _read_stage_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.is_file():
        raise ValueError(f"missing required {label}: {path}")
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _parse_selected_params(value: Any, label: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return {}
    raw = str(value).strip()
    if not raw:
        return {}
    try:
        selected = ast.literal_eval(raw)
    except (SyntaxError, ValueError) as exc:
        raise ValueError(f"{label} is invalid") from exc
    if not isinstance(selected, dict):
        raise ValueError(f"{label} must encode a mapping")
    return selected


def _strict_csv_bool(value: Any, label: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool) and not pd.isna(value):
        if float(value) in {0.0, 1.0}:
            return bool(value)
    text = str(value).strip().casefold()
    if text in {"true", "false"}:
        return text == "true"
    raise ValueError(f"{label} must be boolean")


def _window_id_key(value: Any, label: str) -> str:
    if value is None or isinstance(value, bool) or (isinstance(value, float) and pd.isna(value)):
        raise ValueError(f"{label} must be a window identity")
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    if not text:
        raise ValueError(f"{label} must be a window identity")
    return text


def _date_key(value: Any, label: str) -> str:
    try:
        parsed = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a date") from exc
    if pd.isna(parsed):
        raise ValueError(f"{label} must be a date")
    return parsed.date().isoformat()


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a non-negative integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a non-negative integer") from exc
    if parsed < 0 or float(value) != parsed:
        raise ValueError(f"{label} must be a non-negative integer")
    return parsed


_WFA_EARLY_EXIT_REASONS = {
    "no_in_sample_rows_after_selection_filter",
    "selected_train_net_profit_not_positive",
    "selected_train_profit_factor_below_minimum",
}
_WFA_GRID_METADATA_COLUMNS = {
    "wfa_window_id",
    "wfa_train_start",
    "wfa_train_end",
    "wfa_test_start",
    "wfa_test_end",
    "wfa_objective",
    "wfa_base_config_hash",
    "wfa_parameter_hash",
    "wfa_selection_filter_hash",
    "wfa_input_hash",
    "wfa_selection_rank",
    "wfa_selected",
}


def _runtime_wfa_grid_contract(
    effective_config: dict[str, Any],
    stage_cfg: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime = _merged_section(effective_config, "wfa", stage_cfg)
    runtime.setdefault("mode", "unanchored")
    runtime.setdefault("train_months", 48)
    runtime.setdefault("test_months", 12)
    runtime.setdefault("step_months", 12)
    runtime["objective"] = "MAR"
    runtime.pop("selection_min_trades_per_year", None)
    runtime["selection_exclusive_min_trades_per_year"] = 50
    runtime.setdefault("early_exit_min_train_profit_factor", 1.0)
    return runtime, _wfa_grid_config(runtime)


def _window_number(value: Any, label: str) -> int:
    key = _window_id_key(value, label)
    try:
        number = int(key)
    except ValueError as exc:
        raise ValueError(f"{label} must be a positive producer window number") from exc
    if number <= 0 or key != str(number):
        raise ValueError(f"{label} must be a positive producer window number")
    return number


def _market_timestamp(value: Any, label: str, timezone_name: str) -> pd.Timestamp:
    try:
        parsed = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a valid timestamp") from exc
    if pd.isna(parsed):
        raise ValueError(f"{label} must be a valid timestamp")
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include the producer market offset")
    try:
        market = parsed.tz_convert(ZoneInfo(timezone_name))
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"configured exchange timezone is invalid: {timezone_name}") from exc
    if parsed.tz_localize(None) != market.tz_localize(None):
        raise ValueError(f"{label} is not serialized in configured exchange timezone {timezone_name}")
    return market


def _plain_scalar(value: Any) -> Any:
    return value.item() if hasattr(value, "item") else value


def _require_scalar_equal(actual: Any, expected: Any, label: str) -> None:
    actual = _plain_scalar(actual)
    expected = _plain_scalar(expected)
    if isinstance(actual, (int, float)) and not isinstance(actual, bool):
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            if math.isnan(float(actual)) and math.isnan(float(expected)):
                return
            if float(actual) == float(expected):
                return
    _require_equal(actual, expected, label)


def _validate_wfa_train_grid(
    path: Path,
    *,
    window: dict[str, Any],
    parameters: dict[str, Any],
    grid_config: dict[str, Any],
    effective_config: dict[str, Any],
    canonical_input_hash: str,
) -> dict[str, Any]:
    frame = _read_stage_csv(path, f"WFA window {window['window_id']} train grid")
    if frame.empty:
        raise ValueError(f"WFA train grid is empty: {path.name}")
    missing = sorted(_WFA_GRID_METADATA_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"WFA train grid {path.name} lacks producer columns: {', '.join(missing)}")

    metadata = _train_grid_metadata(effective_config, grid_config, canonical_input_hash)
    expected_metadata = {
        "wfa_window_id": window["window_number"],
        "wfa_train_start": window["train_start"],
        "wfa_train_end": window["train_end"],
        "wfa_test_start": window["test_start"],
        "wfa_test_end": window["test_end"],
        "wfa_objective": _objective_label(grid_config["objective"]),
        "wfa_base_config_hash": metadata["base_config_hash"],
        "wfa_parameter_hash": metadata["parameter_hash"],
        "wfa_selection_filter_hash": metadata["selection_filter_hash"],
        "wfa_input_hash": metadata["input_hash"],
    }
    for column, expected in expected_metadata.items():
        if frame[column].isna().any():
            raise ValueError(f"WFA train grid {path.name} has missing {column}")
        for row_index, actual in frame[column].items():
            if column.endswith("_start") or column.endswith("_end"):
                actual = _date_key(actual, f"WFA train grid {path.name} row {row_index} {column}")
            _require_scalar_equal(
                actual,
                expected,
                f"WFA train grid {path.name} row {row_index} {column}",
            )

    combinations = parameter_combinations(parameters, "wfa.parameters")
    _require_equal(len(frame), len(combinations), f"WFA train grid {path.name} combination count")
    if "run_id" not in frame.columns:
        raise ValueError(f"WFA train grid {path.name} lacks producer run_id")
    missing_parameters = sorted(set(parameters) - set(frame.columns))
    if missing_parameters:
        raise ValueError(f"WFA train grid {path.name} lacks parameter columns: {missing_parameters}")
    actual_combinations = [{name: _plain_scalar(row[name]) for name in parameters} for _, row in frame.iterrows()]
    observed_run_ids: set[int] = set()
    for row_index, (actual, run_id_value) in enumerate(zip(actual_combinations, frame["run_id"], strict=True)):
        run_id = _nonnegative_int(run_id_value, f"WFA train grid {path.name} row {row_index} run_id")
        if run_id <= 0 or run_id > len(combinations) or run_id in observed_run_ids:
            raise ValueError(f"WFA train grid {path.name} contains an invalid or duplicate producer run_id")
        observed_run_ids.add(run_id)
        _require_equal(
            actual,
            combinations[run_id - 1],
            f"WFA train grid {path.name} run_id {run_id} parameter identity",
        )
    _require_equal(
        observed_run_ids,
        set(range(1, len(combinations) + 1)),
        f"WFA train grid {path.name} producer run IDs",
    )
    unmatched = list(combinations)
    for actual in actual_combinations:
        for index, expected in enumerate(unmatched):
            if actual == expected:
                unmatched.pop(index)
                break
        else:
            raise ValueError(f"WFA train grid {path.name} contains a row outside the published parameter grid")
    if unmatched:
        raise ValueError(f"WFA train grid {path.name} omits published parameter combinations")

    objective = grid_config["objective"]
    if objective not in frame.columns:
        raise ValueError(f"WFA train grid {path.name} lacks objective column {objective}")
    sort_columns, ascending = _selection_sort_spec(frame, objective)
    expected_order = frame.sort_values(sort_columns, ascending=ascending, na_position="last").index.tolist()
    if expected_order != frame.index.tolist():
        raise ValueError(f"WFA train grid {path.name} rows are not in canonical selection order")
    ranks = [
        _nonnegative_int(value, f"WFA train grid {path.name} selection rank") for value in frame["wfa_selection_rank"]
    ]
    _require_equal(ranks, list(range(1, len(frame) + 1)), f"WFA train grid {path.name} selection ranks")
    selected_markers = [
        _strict_csv_bool(value, f"WFA train grid {path.name} selected marker") for value in frame["wfa_selected"]
    ]
    _require_equal(
        selected_markers,
        [index == 0 for index in range(len(frame))],
        f"WFA train grid {path.name} canonical rank-one marker",
    )

    best = _select_best_in_sample(frame, objective, grid_config["selection_filter"])
    derived = {name: _plain_scalar(best[name]) for name in parameters}
    _require_equal(derived, window["selected_params"], f"WFA train grid {path.name} selected parameters")
    _require_scalar_equal(
        window["result_row"].get("train_objective"),
        best[objective],
        f"WFA train grid {path.name} selected objective",
    )
    for result_field, grid_field in (
        ("train_mar", "mar"),
        ("train_cagr", "cagr"),
        ("train_max_drawdown_pct", "max_drawdown_pct"),
        ("train_net_profit", "net_profit"),
        ("train_profit_factor", "profit_factor"),
        ("train_max_drawdown", "max_drawdown"),
    ):
        if grid_field not in frame.columns:
            raise ValueError(f"WFA train grid {path.name} lacks selected metric {grid_field}")
        _require_scalar_equal(
            window["result_row"].get(result_field),
            best[grid_field],
            f"WFA train grid {path.name} selected {grid_field}",
        )
    rank_one = {name: _plain_scalar(frame.iloc[0][name]) for name in parameters}
    return {
        "path": path.name,
        "window_id": window["window_id"],
        "combination_count": len(frame),
        "base_config_hash": metadata["base_config_hash"],
        "parameter_hash": metadata["parameter_hash"],
        "selection_filter_hash": metadata["selection_filter_hash"],
        "input_hash": metadata["input_hash"],
        "canonical_rank_one_params": rank_one,
        "derived_selected_params": derived,
    }


def _validate_wfa_execution_evidence(
    results_path: Path,
    trades_path: Path,
    parameters: dict[str, Any],
    canonical_summary: dict[str, Any],
    *,
    artifact_paths: list[Path],
    effective_config: dict[str, Any],
    stage_cfg: dict[str, Any],
    project_root: Path,
    canonical_input_hash: str,
) -> dict[str, Any]:
    results = _read_stage_csv(results_path, "WFA results")
    trades = _read_stage_csv(trades_path, "WFA OOS trade log")
    runtime_wfa, grid_config = _runtime_wfa_grid_contract(effective_config, stage_cfg)
    _require_equal(parameters, grid_config["parameters"], "WFA runtime published parameters")
    _require_equal(canonical_summary.get("objective"), _objective_label(grid_config["objective"]), "WFA objective")
    _require_equal(canonical_summary.get("selection_filter"), grid_config["selection_filter"], "WFA selection filter")
    for field in ("window_mode", "train_months", "test_months", "step_months"):
        expected = _wfa_mode(runtime_wfa) if field == "window_mode" else runtime_wfa[field]
        _require_equal(canonical_summary.get(field), expected, f"WFA {field}")
    _require_equal(canonical_summary.get("parallel"), grid_config["parallel"], "WFA parallel contract")
    _require_equal(
        canonical_summary.get("complete_oos_windows_only"),
        True,
        "WFA complete-window policy",
    )
    early_exit_profit_factor = runtime_wfa["early_exit_min_train_profit_factor"]
    _require_equal(
        canonical_summary.get("early_exit_min_train_profit_factor"),
        float(early_exit_profit_factor) if early_exit_profit_factor is not None else None,
        "WFA early-exit profit-factor threshold",
    )
    _require_equal(
        canonical_summary.get("early_exit_require_train_profitable"),
        bool(runtime_wfa.get("early_exit_require_train_profitable", False)),
        "WFA early-exit profitability control",
    )
    timezone_name = _require_nonempty_string(
        (effective_config.get("data") or {}).get("exchange_timezone")
        or (effective_config.get("data") or {}).get("timezone"),
        "WFA exchange timezone",
    )
    required_result_columns = {
        "window_id",
        "train_start",
        "train_end",
        "test_start",
        "test_end",
        "objective",
        "selected_params",
        "oos_window_complete",
        "oos_evaluated",
        "test_observations",
        "test_first_timestamp",
        "test_last_timestamp",
        "test_trades",
    }
    if not results.empty:
        missing = sorted(required_result_columns - set(results.columns))
        if missing:
            raise ValueError(f"WFA results lack producer columns: {', '.join(missing)}")

    normalized_results = results.copy()
    windows: dict[str, dict[str, Any]] = {}
    ordered_realized: list[dict[str, Any]] = []
    normalized_params: list[dict[str, Any]] = []
    normalized_early_exit: list[bool] = []
    for index, row in results.iterrows():
        window_id = _window_id_key(row.get("window_id"), f"WFA results row {index} window_id")
        window_number = _window_number(row.get("window_id"), f"WFA results row {index} window_id")
        if window_id in windows:
            raise ValueError(f"WFA results contain duplicate window_id {window_id}")
        complete = _strict_csv_bool(
            row.get("oos_window_complete"),
            f"WFA results row {index} oos_window_complete",
        )
        if not complete:
            raise ValueError(f"WFA results row {index} is not a complete OOS window")
        evaluated = _strict_csv_bool(row.get("oos_evaluated"), f"WFA results row {index} oos_evaluated")
        early_exit = (
            _strict_csv_bool(row.get("early_exit"), f"WFA results row {index} early_exit")
            if "early_exit" in results.columns and not pd.isna(row.get("early_exit"))
            else False
        )
        selected = _validate_selected_params(
            _parse_selected_params(row.get("selected_params"), f"WFA results row {index} selected_params"),
            parameters,
            f"WFA results row {index} selected_params",
            require_complete=evaluated,
        )
        if not evaluated and selected:
            raise ValueError(f"WFA unevaluated window {window_id} cannot record selected parameters")
        if evaluated and early_exit:
            raise ValueError(f"WFA evaluated window {window_id} cannot be marked early_exit")
        if not evaluated:
            reason = str(row.get("early_exit_reason") or "").strip()
            if not early_exit or reason not in _WFA_EARLY_EXIT_REASONS:
                raise ValueError(f"WFA unevaluated window {window_id} must be a producer early-exit row")
            if _nonnegative_int(row.get("test_trades"), f"WFA results row {index} test_trades") != 0:
                raise ValueError(f"WFA early-exit window {window_id} cannot record OOS trades")
            if index != len(results) - 1:
                raise ValueError(f"WFA early-exit window {window_id} must terminate retained results")
            for field in (
                "test_mar",
                "test_cagr",
                "test_max_drawdown_pct",
                "test_net_profit",
                "test_profit_factor",
                "test_max_drawdown",
            ):
                _require_scalar_equal(row.get(field), 0.0, f"WFA early-exit window {window_id} {field}")
            _require_equal(
                _strict_csv_bool(row.get("test_passed"), f"WFA early-exit window {window_id} test_passed"),
                False,
                f"WFA early-exit window {window_id} test_passed",
            )
        _require_equal(
            str(row.get("objective")),
            _objective_label(grid_config["objective"]),
            f"WFA results row {index} objective",
        )
        first_timestamp = _market_timestamp(
            row.get("test_first_timestamp"),
            f"WFA results row {index} test_first_timestamp",
            timezone_name,
        )
        last_timestamp = _market_timestamp(
            row.get("test_last_timestamp"),
            f"WFA results row {index} test_last_timestamp",
            timezone_name,
        )
        if last_timestamp < first_timestamp:
            raise ValueError(f"WFA results row {index} test timestamps are reversed")
        record = {
            "window_id": window_id,
            "window_number": window_number,
            "train_start": _date_key(row.get("train_start"), f"WFA results row {index} train_start"),
            "train_end": _date_key(row.get("train_end"), f"WFA results row {index} train_end"),
            "test_start": _date_key(row.get("test_start"), f"WFA results row {index} test_start"),
            "test_end": _date_key(row.get("test_end"), f"WFA results row {index} test_end"),
            "selected_params": selected,
            "oos_evaluated": evaluated,
            "early_exit": early_exit,
            "test_observations": _nonnegative_int(
                row.get("test_observations"), f"WFA results row {index} test_observations"
            ),
            "test_trades": _nonnegative_int(row.get("test_trades"), f"WFA results row {index} test_trades"),
            "test_first_timestamp": first_timestamp,
            "test_last_timestamp": last_timestamp,
            "result_row": row,
        }
        if record["test_observations"] <= 0:
            raise ValueError(f"WFA retained window {window_id} must have positive test observations")
        if record["train_start"] >= record["train_end"] or record["test_start"] >= record["test_end"]:
            raise ValueError(f"WFA window {window_id} must contain valid half-open train/test intervals")
        if record["train_end"] != record["test_start"]:
            raise ValueError(f"WFA window {window_id} train and test intervals must be contiguous")
        if pd.Timestamp(record["test_start"]) + pd.DateOffset(months=int(runtime_wfa["test_months"])) != pd.Timestamp(
            record["test_end"]
        ):
            raise ValueError(f"WFA window {window_id} test interval disagrees with the frozen calendar length")
        if _wfa_mode(runtime_wfa) == "unanchored" and pd.Timestamp(record["train_start"]) + pd.DateOffset(
            months=int(runtime_wfa["train_months"])
        ) != pd.Timestamp(record["train_end"]):
            raise ValueError(f"WFA window {window_id} train interval disagrees with the frozen calendar length")
        test_start = pd.Timestamp(record["test_start"])
        test_end = pd.Timestamp(record["test_end"])
        if not (test_start <= first_timestamp.tz_localize(None) <= last_timestamp.tz_localize(None) < test_end):
            raise ValueError(f"WFA window {window_id} retained test timestamps fall outside its test interval")
        windows[window_id] = record
        if evaluated:
            ordered_realized.append(record)
        normalized_params.append(selected)
        normalized_early_exit.append(early_exit)

    producer_intervals = [
        {
            "window_id": window["window_number"],
            "test_start": window["test_start"],
            "test_end": window["test_end"],
        }
        for window in windows.values()
    ]
    _require_equal(
        [window["window_number"] for window in windows.values()],
        sorted(window["window_number"] for window in windows.values()),
        "WFA retained window order",
    )
    _validate_oos_intervals(producer_intervals)

    if not normalized_results.empty:
        normalized_results["selected_params"] = normalized_params
        normalized_results["early_exit"] = normalized_early_exit
    derived_incubation = _select_incubation_params(normalized_results)
    derived_incubation = _validate_selected_params(
        derived_incubation,
        parameters,
        "WFA derived incubation selected parameters",
        require_complete=bool(derived_incubation),
    )
    _require_equal(
        canonical_summary.get("incubation_selected_params"),
        derived_incubation,
        "WFA deterministic incubation selection",
    )

    trade_records: list[dict[str, Any]] = []
    counts = {window_id: 0 for window_id in windows}
    if not trades.empty:
        required_trade_columns = {
            "wfa_window_id",
            "wfa_train_start",
            "wfa_train_end",
            "wfa_test_start",
            "wfa_test_end",
            "wfa_objective",
            "wfa_train_objective",
            "wfa_selected_params",
            "entry_timestamp",
        }
        missing = sorted(required_trade_columns - set(trades.columns))
        if missing:
            raise ValueError(f"WFA OOS trade log lacks producer columns: {', '.join(missing)}")
        for index, row in trades.iterrows():
            window_id = _window_id_key(
                row.get("wfa_window_id"),
                f"WFA OOS trade row {index} wfa_window_id",
            )
            window = windows.get(window_id)
            if window is None:
                raise ValueError(f"WFA OOS trade row {index} references unknown window {window_id}")
            if not window["oos_evaluated"]:
                raise ValueError(f"WFA OOS trade row {index} references unevaluated window {window_id}")
            selected = _validate_selected_params(
                _parse_selected_params(
                    row.get("wfa_selected_params"),
                    f"WFA OOS trade row {index} wfa_selected_params",
                ),
                parameters,
                f"WFA OOS trade row {index} wfa_selected_params",
                require_complete=True,
            )
            _require_equal(selected, window["selected_params"], f"WFA OOS trade row {index} window selection")
            _require_equal(
                _date_key(row.get("wfa_test_start"), f"WFA OOS trade row {index} wfa_test_start"),
                window["test_start"],
                f"WFA OOS trade row {index} test start",
            )
            _require_equal(
                _date_key(row.get("wfa_test_end"), f"WFA OOS trade row {index} wfa_test_end"),
                window["test_end"],
                f"WFA OOS trade row {index} test end",
            )
            for field in ("train_start", "train_end"):
                _require_equal(
                    _date_key(row.get(f"wfa_{field}"), f"WFA OOS trade row {index} wfa_{field}"),
                    window[field],
                    f"WFA OOS trade row {index} {field.replace('_', ' ')}",
                )
            _require_equal(
                str(row.get("wfa_objective")),
                _objective_label(grid_config["objective"]),
                f"WFA OOS trade row {index} objective",
            )
            _require_scalar_equal(
                row.get("wfa_train_objective"),
                window["result_row"].get("train_objective"),
                f"WFA OOS trade row {index} train objective",
            )
            entry = _market_timestamp(
                row.get("entry_timestamp"),
                f"WFA OOS trade row {index} entry_timestamp",
                timezone_name,
            )
            if not (pd.Timestamp(window["test_start"]) <= entry.tz_localize(None) < pd.Timestamp(window["test_end"])):
                raise ValueError(f"WFA OOS trade row {index} entry falls outside its half-open test interval")
            counts[window_id] += 1
            trade_records.append(
                {
                    "window_id": window_id,
                    "entry_timestamp": entry.isoformat(),
                    "selected_params": selected,
                }
            )

        _validate_stitched_oos_trade_identity(
            trades,
            [item for item in producer_intervals if windows[str(item["window_id"])]["oos_evaluated"]],
        )

    for window_id, window in windows.items():
        _require_equal(counts[window_id], window["test_trades"], f"WFA window {window_id} trade count")

    _require_equal(canonical_summary.get("windows"), len(results), "WFA summary window count")
    _require_equal(
        canonical_summary.get("realized_oos_windows"),
        len(ordered_realized),
        "WFA summary realized window count",
    )
    _require_equal(
        canonical_summary.get("realized_oos_trades"),
        len(trades),
        "WFA summary realized trade count",
    )
    _require_equal(canonical_summary.get("stitched_oos_trades"), len(trades), "WFA stitched trade count")
    planned_windows = _nonnegative_int(
        canonical_summary.get("planned_complete_oos_windows"),
        "WFA planned complete OOS windows",
    )
    if planned_windows < len(results):
        raise ValueError("WFA planned window count is smaller than retained results")
    _require_equal(
        canonical_summary.get("skipped_complete_oos_windows"),
        planned_windows - len(ordered_realized),
        "WFA skipped complete OOS windows",
    )
    _require_equal(
        canonical_summary.get("realized_oos_observations"),
        sum(item["test_observations"] for item in ordered_realized),
        "WFA realized OOS observations",
    )
    _require_equal(
        canonical_summary.get("realized_oos_start"),
        min((item["test_start"] for item in ordered_realized), default=None),
        "WFA realized OOS start",
    )
    _require_equal(
        canonical_summary.get("realized_oos_end"),
        max((item["test_end"] for item in ordered_realized), default=None),
        "WFA realized OOS end",
    )
    _require_equal(
        canonical_summary.get("early_exit"),
        any(item["early_exit"] for item in windows.values()),
        "WFA early-exit summary",
    )
    intervals = canonical_summary.get("realized_oos_intervals")
    if not isinstance(intervals, list):
        raise ValueError("WFA realized_oos_intervals must be a list")
    _require_equal(len(intervals), len(ordered_realized), "WFA realized interval count")
    for index, (interval, realized) in enumerate(zip(intervals, ordered_realized, strict=True)):
        if not isinstance(interval, dict):
            raise ValueError(f"WFA realized interval {index} must be a mapping")
        _require_equal(
            _window_id_key(interval.get("window_id"), f"WFA realized interval {index} window_id"),
            realized["window_id"],
            f"WFA realized interval {index} window",
        )
        for field in ("test_start", "test_end"):
            _require_equal(
                _date_key(interval.get(field), f"WFA realized interval {index} {field}"),
                realized[field],
                f"WFA realized interval {index} {field}",
            )
        _require_equal(
            _nonnegative_int(interval.get("observations"), f"WFA realized interval {index} observations"),
            realized["test_observations"],
            f"WFA realized interval {index} observations",
        )
        _require_equal(
            _nonnegative_int(interval.get("trades"), f"WFA realized interval {index} trades"),
            realized["test_trades"],
            f"WFA realized interval {index} trades",
        )
        for field in ("first_timestamp", "last_timestamp"):
            _require_equal(
                _market_timestamp(
                    interval.get(field),
                    f"WFA realized interval {index} {field}",
                    timezone_name,
                ),
                realized[f"test_{field}"],
                f"WFA realized interval {index} {field}",
            )

    canonical_grid_files = canonical_summary.get("train_grid_report_files")
    if not isinstance(canonical_grid_files, list):
        raise ValueError("WFA train_grid_report_files must be a list")
    stage_dir = results_path.parent.resolve()
    resolved_grid_files = [
        _resolve_reference(value, project_root, f"WFA train_grid_report_files[{index}]")
        for index, value in enumerate(canonical_grid_files)
    ]
    if len(resolved_grid_files) != len(set(resolved_grid_files)):
        raise ValueError("WFA train_grid_report_files contains duplicate paths")
    expected_grid_files = [
        stage_dir / f"window_{window['window_number']:03d}_train_grid.csv" for window in ordered_realized
    ]
    _require_equal(resolved_grid_files, expected_grid_files, "WFA canonical train-grid report files")
    actual_grid_files = sorted(path.resolve() for path in stage_dir.glob("window_*_train_grid.csv") if path.is_file())
    _require_equal(actual_grid_files, sorted(expected_grid_files), "WFA retained train-grid file set")
    artifact_set = {path.resolve() for path in artifact_paths}
    if any(path not in artifact_set for path in expected_grid_files):
        raise ValueError("WFA train-grid report is absent from the stage artifact inventory")
    _require_equal(
        canonical_summary.get("train_grid_reports_retained"),
        True,
        "WFA train-grid retention flag",
    )
    train_grid_bindings = [
        _validate_wfa_train_grid(
            path,
            window=window,
            parameters=parameters,
            grid_config=grid_config,
            effective_config=effective_config,
            canonical_input_hash=canonical_input_hash,
        )
        for path, window in zip(expected_grid_files, ordered_realized, strict=True)
    ]
    return {
        "runtime_wfa": {
            "objective": _objective_label(grid_config["objective"]),
            "selection_filter": deepcopy(grid_config["selection_filter"]),
            "exchange_timezone": timezone_name,
            "window_mode": _wfa_mode(runtime_wfa),
            "train_months": runtime_wfa["train_months"],
            "test_months": runtime_wfa["test_months"],
            "step_months": runtime_wfa["step_months"],
        },
        "incubation_selected_params": derived_incubation,
        "window_selections": [
            {"window_id": value["window_id"], "selected_params": value["selected_params"]} for value in windows.values()
        ],
        "trade_selections": trade_records,
        "train_grid_bindings": train_grid_bindings,
    }


def _validate_stage_execution_config(
    *,
    stage: str,
    stage_cfg: dict[str, Any],
    canonical_summary: dict[str, Any],
    artifact_paths: list[Path],
    effective_config: dict[str, Any],
    project_root: Path,
    canonical_input_hash: str,
) -> dict[str, Any]:
    if stage == "limited_core_grid_test":
        parameters = _published_parameter_grid(effective_config, "core_grid", stage_cfg)
        _require_equal(
            canonical_summary.get("parameter_mode"),
            "fixed_config" if not parameters else "predeclared_optimization",
            "limited core canonical parameter mode",
        )
        _require_equal(
            canonical_summary.get("parameter_value_counts"),
            {name: len(values) for name, values in parameters.items()},
            "limited core canonical parameter value counts",
        )
        combinations = _expected_combination_count(parameters)
        _require_equal(
            canonical_summary.get("expected_combinations"),
            combinations,
            "limited core canonical expected combinations",
        )
        _require_equal(
            canonical_summary.get("total_combinations_tested"),
            combinations,
            "limited core canonical tested combinations",
        )
        fixed = canonical_summary.get("fixed_config_core")
        if not isinstance(fixed, dict):
            raise ValueError("limited core canonical fixed_config_core must be a mapping")
        _require_equal(fixed.get("purpose"), "fixed_config_mechanics_cross_check", "limited core fixed purpose")
        _require_equal(
            fixed.get("parameter_source"),
            "strategy section in effective config",
            "limited core fixed parameter source",
        )
        _require_equal(fixed.get("uses_grid_selected_params"), False, "limited core fixed grid-selected flag")
        _require_equal(fixed.get("core"), effective_config.get("core"), "limited core fixed core snapshot")
        _require_equal(fixed.get("strategy"), effective_config.get("strategy"), "limited core fixed strategy snapshot")
        reproducibility = fixed.get("reproducibility")
        if not isinstance(reproducibility, dict):
            raise ValueError("limited core fixed reproducibility must be a mapping")
        engine_config_hash = object_sha256(effective_config)
        _require_equal(
            reproducibility.get("config_hash"),
            engine_config_hash,
            "limited core fixed engine config hash",
        )
        subordinate_paths = [path for path in artifact_paths if path.name == "fixed_config_core_metrics.json"]
        _require_equal(len(subordinate_paths), 1, "limited core fixed metrics artifact count")
        subordinate = _read_json(subordinate_paths[0], "limited core fixed metrics")
        _require_equal(subordinate, fixed, "limited core complete fixed metrics projection")
        return {
            "fixed_config_core": {
                "core": deepcopy(fixed["core"]),
                "strategy": deepcopy(fixed["strategy"]),
                "engine_config_hash": engine_config_hash,
            },
            "grid": {
                "parameter_mode": canonical_summary["parameter_mode"],
                "parameter_value_counts": deepcopy(canonical_summary["parameter_value_counts"]),
                "expected_combinations": combinations,
            },
        }
    if stage == "walk_forward_analysis":
        parameters = _published_parameter_grid(effective_config, "wfa", stage_cfg)
        _require_equal(
            canonical_summary.get("parameter_mode"),
            "fixed_config" if not parameters else "predeclared_optimization",
            "WFA canonical parameter mode",
        )
        results_paths = [path for path in artifact_paths if path.name == "wfa_results.csv"]
        trade_paths = [path for path in artifact_paths if path.name == "wfa_oos_trade_log.csv"]
        _require_equal(len(results_paths), 1, "WFA results artifact count")
        _require_equal(len(trade_paths), 1, "WFA trade-log artifact count")
        evidence = _validate_wfa_execution_evidence(
            results_paths[0],
            trade_paths[0],
            parameters,
            canonical_summary,
            artifact_paths=artifact_paths,
            effective_config=effective_config,
            stage_cfg=stage_cfg,
            project_root=project_root,
            canonical_input_hash=canonical_input_hash,
        )
        return {
            "wfa_grid": deepcopy(parameters),
            **evidence,
        }
    return {}


def _completed_stage_projection(
    item: dict[str, Any],
    *,
    stage: str,
    stage_dir: Path,
    stage_cfg: dict[str, Any],
    effective_config: dict[str, Any],
    canonical_input_hash: str,
) -> tuple[dict[str, Any], list[str]]:
    expected_keys = _STAGE_COMMON_KEYS | _COMPLETED_STAGE_PAYLOAD_KEYS[stage]
    _require_equal(set(item), expected_keys, f"{stage} completed payload fields")
    projected = deepcopy(item)
    omitted: list[str] = []
    if stage in _DATA_BEARING_STAGES:
        _require_equal(item.get("input_hash"), canonical_input_hash, f"{stage} input hash")
        quality, quality_omitted = _data_quality_projection(stage_dir, item.get("data_quality"))
        projected["data_quality"] = quality
        omitted.extend(f"data_quality.{field}" for field in quality_omitted)
    if stage == "limited_core_grid_test":
        parameters = _published_parameter_grid(effective_config, "core_grid", stage_cfg)
        _require_equal(item.get("core_grid_parameters"), parameters, "limited core grid parameters")
    if stage == "limited_monkey_test":
        limited_core_cfg = (effective_config.get("campaign_tests") or {}).get("limited_core_grid_test") or {}
        parameters = _published_parameter_grid(effective_config, "core_grid", limited_core_cfg)
        _validate_selected_params(item.get("selected_core_params"), parameters, "limited monkey selected parameters")
    return projected, omitted


def _stage_bindings(
    run_dir: Path,
    effective_config: dict[str, Any],
    summary: dict[str, Any],
    manifest: dict[str, Any],
    project_root: Path,
    canonical_input_hash: str,
    execution_assumptions: dict[str, Any],
) -> list[dict[str, Any]]:
    stages = summary.get("stages")
    if not isinstance(stages, list) or not all(isinstance(item, dict) for item in stages):
        raise ValueError("campaign summary stages must be a list of objects")
    names = [item.get("stage") for item in stages]
    _require_equal(names, PRE_ACCEPTANCE_STAGE_ORDER, "pre-acceptance stage order")
    _require_equal(manifest.get("stage_order"), PRE_ACCEPTANCE_STAGE_ORDER, "manifest stage order")
    run_created_at = _require_aware_datetime(summary.get("created_at"), "summary created_at")
    previous_completed_at: datetime | None = None
    bindings: list[dict[str, Any]] = []
    for item in stages:
        stage = str(item["stage"])
        validate_stage_result_contract(item, context=f"campaign summary stage {stage}")
        status = str(item.get("status"))
        _require_equal(item.get("label"), STAGE_LABELS.get(stage, stage), f"{stage} label")
        if (status == "passed") != (item.get("passed") is True):
            raise ValueError(f"{stage} status and passed flag are inconsistent")
        criteria = item.get("criteria") or []
        stage_cfg = (effective_config.get("campaign_tests") or {}).get(stage) or {}
        criteria_contract = _frozen_stage_criteria(stage, stage_cfg)
        projected_item = deepcopy(item)
        omitted_unverified_fields: list[str] = []
        validated_execution_config_snapshots: dict[str, Any] = {}
        validated_engine_config_hashes: list[dict[str, str]] = []
        if status == "skipped":
            _require_equal(stage_cfg.get("enabled"), False, f"{stage} disabled stage config")
            expected_skipped = _annotate_stage_decisions(_skipped_stage(stage, "disabled"))
            _require_equal(item, expected_skipped, f"{stage} disabled producer result")
        else:
            _require_equal(len(criteria), len(criteria_contract), f"{stage} criteria count")
        annotated = _annotate_stage_decisions(deepcopy(item))
        for field in (
            "scientific_validity_verdict",
            "scientific_validity_passed",
            "generic_objective_verdict",
            "generic_objective_passed",
        ):
            _require_equal(item.get(field), annotated.get(field), f"{stage} {field}")
        if status in {"passed", "failed"}:
            if not criteria:
                raise ValueError(f"{stage} completed result requires non-empty criteria")
            expected_passed = all(criterion.get("passed") is True for criterion in criteria)
            _require_equal(item.get("passed"), expected_passed, f"{stage} criteria aggregate")
            _require_equal(status, "passed" if expected_passed else "failed", f"{stage} criteria status")
            started_at = _require_aware_datetime(item.get("started_at"), f"{stage} started_at")
            completed_at = _require_aware_datetime(item.get("completed_at"), f"{stage} completed_at")
            if completed_at < started_at:
                raise ValueError(f"{stage} completed_at precedes started_at")
            if previous_completed_at is not None and started_at < previous_completed_at:
                raise ValueError(f"{stage} started_at precedes the prior completed stage")
            if completed_at > run_created_at:
                raise ValueError(f"{stage} completed_at follows the run summary timestamp")
            duration = item.get("duration_seconds")
            if (
                isinstance(duration, bool)
                or not isinstance(duration, (int, float))
                or not math.isfinite(float(duration))
                or duration < 0
            ):
                raise ValueError(f"{stage} duration_seconds must be non-negative")
            elapsed = (completed_at - started_at).total_seconds()
            if abs(float(duration) - elapsed) > _DURATION_TOLERANCE_SECONDS:
                raise ValueError(
                    f"{stage} duration_seconds disagrees with timestamps beyond "
                    f"{_DURATION_TOLERANCE_SECONDS:g}s tolerance"
                )
            previous_completed_at = completed_at
            if item.get("error") is not None or item.get("skip_reason") is not None:
                raise ValueError(f"{stage} completed result cannot record error or skip_reason")
            expected_criteria = evaluate_criteria(item, criteria_contract)
            _require_equal(criteria, expected_criteria, f"{stage} authoritative criteria")
        if status == "error" and not str(item.get("error") or "").strip():
            raise ValueError(f"{stage} error status requires a non-empty error")
        if status == "error":
            _require_equal(
                set(item),
                {
                    "stage",
                    "label",
                    "status",
                    "passed",
                    "error",
                    "criteria",
                    "scientific_validity_verdict",
                    "scientific_validity_passed",
                    "generic_objective_verdict",
                    "generic_objective_passed",
                },
                f"{stage} error payload fields",
            )
            if not criteria:
                raise ValueError(f"{stage} error result must retain producer criteria")
            expected_error_criteria = evaluate_criteria(
                {"stage": stage, "error": str(item["error"])},
                criteria_contract,
            )
            _require_equal(criteria, expected_error_criteria, f"{stage} error criteria")
            if item.get("artifacts") is not None or item.get("skip_reason") is not None:
                raise ValueError(f"{stage} error result cannot record artifacts or skip_reason")
        if status == "skipped" and not str(item.get("skip_reason") or "").strip():
            raise ValueError(f"{stage} skipped status requires a non-empty skip_reason")
        if status == "skipped" and (criteria or item.get("artifacts") is not None or item.get("error") is not None):
            raise ValueError(f"{stage} skipped result cannot record criteria, artifacts, or error")
        result_path = run_dir / stage / "stage_result.json"
        if result_path.is_file():
            result = _read_json(result_path, f"{stage} stage result")
            validate_stage_result_contract(result, context=f"{stage}/stage_result.json")
            _require_equal(result, item, f"{stage} stage result")
            artifacts_value = result.get("artifacts")
            if status in {"passed", "failed"} and (not isinstance(artifacts_value, list) or not artifacts_value):
                raise ValueError(f"{stage} completed result requires a non-empty artifacts list")
            artifact_bindings: list[dict[str, Any]] = []
            artifact_paths: list[Path] = []
            if artifacts_value is not None:
                if not isinstance(artifacts_value, list):
                    raise ValueError(f"{stage}.artifacts must be a list when present")
                for index, value in enumerate(artifacts_value):
                    artifact_path = _resolve_reference(value, project_root, f"{stage}.artifacts[{index}]")
                    if not _is_relative_to(artifact_path, (run_dir / stage).resolve()):
                        raise ValueError(f"{stage} artifact is outside its stage directory: {value}")
                    artifact_bindings.append(_artifact(artifact_path, project_root=project_root))
                    artifact_paths.append(artifact_path)
            if status in {"passed", "failed"}:
                recorded = {item["path"] for item in artifact_bindings}
                actual = {
                    _artifact(path, project_root=project_root)["path"]
                    for path in (run_dir / stage).rglob("*")
                    if path.is_file() and path.name != "stage_result.json"
                }
                _require_equal(recorded, actual, f"{stage} referenced artifact inventory")
                canonical_path = run_dir / stage / _CANONICAL_STAGE_SUMMARIES[stage]
                canonical_summary = _read_json(canonical_path, f"{stage} canonical summary")
                _require_equal(item.get("summary"), canonical_summary, f"{stage} canonical summary projection")
                projected_item, omitted_unverified_fields = _completed_stage_projection(
                    item,
                    stage=stage,
                    stage_dir=run_dir / stage,
                    stage_cfg=stage_cfg,
                    effective_config=effective_config,
                    canonical_input_hash=canonical_input_hash,
                )
                _validate_execution_assumptions(
                    stage,
                    canonical_summary,
                    artifact_paths,
                    execution_assumptions,
                )
                validated_execution_config_snapshots = _validate_stage_execution_config(
                    stage=stage,
                    stage_cfg=stage_cfg,
                    canonical_summary=canonical_summary,
                    artifact_paths=artifact_paths,
                    effective_config=effective_config,
                    project_root=project_root,
                    canonical_input_hash=canonical_input_hash,
                )
                validated_engine_config_hashes = _validate_engine_config_hashes(
                    stage,
                    canonical_summary,
                    artifact_paths,
                    effective_config,
                )
                if stage == "walk_forward_analysis":
                    for field in ("stitched_oos_metrics", "incubation_selected_params"):
                        _require_equal(item.get(field), canonical_summary.get(field), f"{stage} {field} projection")
                if stage == "simulated_incubation_core":
                    for field in ("metrics", "diagnostics", "selected_params"):
                        _require_equal(item.get(field), canonical_summary.get(field), f"{stage} {field} projection")
                if stage == "limited_monkey_test":
                    for field in ("selected_core_params", "selected_core_row"):
                        _require_equal(item.get(field), canonical_summary.get(field), f"{stage} {field} projection")
            bindings.append(
                {
                    "summary": projected_item,
                    "stage_result": deepcopy(projected_item),
                    "artifact": _artifact(result_path, project_root=project_root),
                    "referenced_artifacts": artifact_bindings,
                    "missing_stage_result_reason": None,
                    "omitted_unverified_fields": omitted_unverified_fields,
                    "validated_execution_config_snapshots": validated_execution_config_snapshots,
                    "validated_engine_config_hashes": validated_engine_config_hashes,
                }
            )
            continue
        if item.get("status") != "skipped" or not str(item.get("skip_reason") or "").strip():
            raise ValueError(f"missing stage_result.json for non-skipped stage: {stage}")
        bindings.append(
            {
                "summary": deepcopy(item),
                "stage_result": None,
                "artifact": None,
                "referenced_artifacts": [],
                "missing_stage_result_reason": str(item["skip_reason"]),
                "omitted_unverified_fields": [],
                "validated_execution_config_snapshots": {},
                "validated_engine_config_hashes": [],
            }
        )
    return bindings


def build_diagnostic_index(
    *,
    project_root: str | Path,
    run_dir: str | Path,
    preflight_receipt: str | Path,
    mode: str,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    run = Path(run_dir)
    run = run.resolve() if run.is_absolute() else (root / run).resolve()
    if mode not in {"synthetic", "unverified"}:
        raise ValueError("mode must be 'synthetic' or 'unverified'; positive real-origin classification is unsupported")
    if not run.is_dir():
        raise ValueError(f"run directory does not exist: {run}")

    summary_path = run / "campaign_test_summary.json"
    variant_summary_path = run / "variant_test_summary.json"
    manifest_path = run / "run_manifest.json"
    summary = _read_json(summary_path, "campaign summary")
    variant_summary = _read_json(variant_summary_path, "variant summary")
    manifest = _read_json(manifest_path, "run manifest")
    _require_equal(variant_summary, summary, "variant summary")
    validate_run_summary_contract(summary, context="campaign_test_summary.json")

    for key in ("diagnostic_only", "skip_validation", "fast_runtime_defaults", "passed", "halted"):
        if not isinstance(summary.get(key), bool):
            raise ValueError(f"summary.{key} must be boolean")
    _require_equal(summary.get("diagnostic_only"), True, "diagnostic_only")
    _require_equal(summary.get("skip_validation"), False, "skip_validation")
    _require_equal(summary.get("fast_runtime_defaults"), False, "fast_runtime_defaults")
    _require_equal(summary.get("diagnostic_reasons"), [DIAGNOSTIC_REASON], "diagnostic reasons")
    _require_equal(summary.get("research_verdict"), "NEEDS MANUAL REVIEW", "research verdict")
    _require_equal(summary.get("generic_objective_verdict"), "NEEDS MANUAL REVIEW", "generic objective verdict")
    _require_equal(summary.get("scientific_validity_verdict"), "NEEDS MANUAL REVIEW", "scientific validity verdict")
    _require_equal(summary.get("passed"), False, "run passed flag")
    _require_equal(summary.get("halted"), False, "run halted flag")
    preflight = summary.get("submission_preflight")
    if not isinstance(preflight, dict) or preflight.get("passed") is not True or preflight.get("failures"):
        raise ValueError("submission preflight must be successful and record no failures")
    _require_equal(manifest.get("submission_preflight"), preflight, "manifest submission preflight")
    for key in (
        "diagnostic_only",
        "diagnostic_reasons",
        "research_verdict",
        "generic_objective_verdict",
        "scientific_validity_verdict",
        "authoritative_parallel_workers",
        "authoritative_core_grid_workers",
    ):
        _require_equal(manifest.get(key), summary.get(key), f"manifest {key}")
    if not isinstance(manifest.get("diagnostic_only"), bool):
        raise ValueError("manifest.diagnostic_only must be boolean")

    effective_path = run / "effective_config.yaml"
    snapshot_path = run / "source_config.yaml"
    effective_config = _read_yaml(effective_path, "effective config")
    source_config = _read_yaml(snapshot_path, "source config snapshot")
    validate_campaign_config_contract(source_config, context="source_config.yaml")
    validate_campaign_config_contract(effective_config, context="effective_config.yaml")
    _require_equal(file_sha256(effective_path), summary.get("config_hash"), "effective config hash")
    _require_equal(file_sha256(snapshot_path), summary.get("source_config_hash"), "source config snapshot hash")
    for key, expected in (
        ("config_path", effective_path),
        ("effective_config_path", effective_path),
        ("source_config_snapshot_path", snapshot_path),
    ):
        _require_equal(_resolve_reference(summary.get(key), root, key), expected.resolve(), key)
    _require_equal(
        _resolve_reference(manifest.get("effective_config"), root, "manifest effective_config"),
        effective_path.resolve(),
        "manifest effective config path",
    )
    _require_equal(
        _resolve_reference(manifest.get("source_config_snapshot"), root, "manifest source_config_snapshot"),
        snapshot_path.resolve(),
        "manifest source config snapshot path",
    )
    _require_equal(manifest.get("config_hash"), summary.get("config_hash"), "manifest effective config hash")
    _require_equal(manifest.get("source_config_hash"), summary.get("source_config_hash"), "manifest source config hash")
    source_path = _resolve_reference(summary.get("source_config_path"), root, "authored source config")
    _require_equal(file_sha256(source_path), summary.get("source_config_hash"), "authored source config hash")
    _require_equal(
        _resolve_reference(manifest.get("config_source"), root, "manifest config_source"),
        source_path,
        "manifest source config path",
    )
    _bind_identities(source_config, effective_config, summary, manifest)
    _require_equal(
        effective_config,
        _expected_effective_config(source_config, summary),
        "effective config canonicalization",
    )
    _require_run_location(
        run,
        project_root=root,
        effective_config=effective_config,
        effective_path=effective_path,
    )
    _require_equal(_resolve_reference(summary.get("output_dir"), root, "summary output_dir"), run, "summary output_dir")
    run_uid_path = run / "run_uid.txt"
    _artifact(run_uid_path, project_root=root)
    run_uid = _require_nonempty_string(run_uid_path.read_text(encoding="utf-8").strip(), "run_uid.txt")
    _require_equal(run_uid, summary.get("run_uid"), "run UID marker")

    dataset = _dataset_binding(source_config, summary, root)
    authoring = _authoring_binding(source_path, source_config, dataset["manifest_document"], root)
    mechanics = _mechanics_bindings(
        source_config,
        source_path,
        summary,
        manifest,
        root,
        dataset["canonical_file"]["sha256"],
    )
    producer_bindings = _bind_run_manifest(run, source_path, source_config, effective_config, summary, manifest, root)
    engine_execution_assumptions = ExecutionAssumptions.from_core_config(effective_config.get("core") or {}).as_dict()
    stages = _stage_bindings(
        run,
        effective_config,
        summary,
        manifest,
        root,
        dataset["canonical_file"]["sha256"],
        engine_execution_assumptions,
    )
    _require_equal(
        summary.get("research_verdict"),
        _research_verdict(summary["stages"], summary["diagnostic_reasons"]),
        "producer research verdict",
    )
    _require_equal(
        summary.get("scientific_validity_verdict"),
        _scientific_validity_verdict(summary["stages"], summary["diagnostic_reasons"]),
        "producer scientific-validity verdict",
    )
    receipt = Path(preflight_receipt)
    receipt = receipt.resolve() if receipt.is_absolute() else (root / receipt).resolve()
    preflight_binding = _preflight_binding(receipt, source_path, preflight, root)

    campaign_document = authoring.pop("_campaign_document")
    campaign_artifact = authoring.pop("_campaign_artifact")
    classification, labels = _derive_diagnostic_classification(
        source_config=source_config,
        source_artifact=_artifact(source_path, project_root=root),
        campaign=campaign_document,
        campaign_artifact=campaign_artifact,
        mechanics=mechanics,
    )
    explicit_synthetic = classification["classification"] == "SYNTHETIC_OR_SIMULATED_CONTEXT"
    if explicit_synthetic and mode != "synthetic":
        raise ValueError("explicit simulated fixture classification requires mode='synthetic'")
    if not explicit_synthetic and mode == "synthetic":
        raise ValueError("synthetic mode requires an explicit governed synthetic/simulated classification")
    return {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "input_classification": classification,
        "overall_verdict": "NEEDS MANUAL REVIEW",
        "passed": False,
        "labels": labels,
        "assurance": {
            "source_review_verified": False,
            "implementation_admission_verified": False,
            "data_origin_verified": False,
            "mechanics_gate_currently_revalidated": False,
            "human_mechanics_authority_verified": False,
            "repository_engineering_tests_verified": False,
            "canonical_result_bundle_finalized": False,
            "scientific_pass_or_fail_claimed": False,
            "candidate_promoted": False,
            "trading_ready": False,
            "p3_qualified": False,
        },
        "run_identity": {field: summary.get(field) for field in _IDENTITY_FIELDS},
        "run_controls": {
            "diagnostic_only": True,
            "diagnostic_reasons": [DIAGNOSTIC_REASON],
            "skip_validation": False,
            "fast_runtime_defaults": False,
            "submission_preflight": deepcopy(preflight),
        },
        "preflight": preflight_binding,
        "source_config": {
            "authored": _artifact(source_path, project_root=root),
            "snapshot": _artifact(snapshot_path, project_root=root),
            "effective": _artifact(effective_path, project_root=root),
        },
        "execution_contract": {
            "mechanic": strategy_mechanic(effective_config),
            "strategy": deepcopy(effective_config["strategy"]),
            "engine_execution_assumptions": engine_execution_assumptions,
            "core_grid_parameters": deepcopy((effective_config.get("core_grid") or {}).get("parameters") or {}),
            "wfa_parameters": deepcopy((effective_config.get("wfa") or {}).get("parameters") or {}),
        },
        "authoring": authoring,
        "dataset": dataset,
        "mechanics": mechanics,
        "producer_bindings": producer_bindings,
        "stages": stages,
        "stage_outcomes_retained": True,
        "run_manifest": _artifact(manifest_path, project_root=root),
        "campaign_summary": _artifact(summary_path, project_root=root),
        "variant_summary": _artifact(variant_summary_path, project_root=root),
        "run_artifacts": _inventory_run(run, root),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--preflight-receipt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", required=True, choices=("synthetic", "unverified"))
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    run = Path(args.run_dir)
    run = run.resolve() if run.is_absolute() else (root / run).resolve()
    output = Path(args.output)
    output = output.resolve() if output.is_absolute() else (root / output).resolve()
    try:
        output.relative_to(run)
    except ValueError:
        pass
    else:
        raise ValueError("diagnostic index output must be outside the run directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    document = build_diagnostic_index(
        project_root=root,
        run_dir=run,
        preflight_receipt=args.preflight_receipt,
        mode=args.mode,
    )
    with output.open("x", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(output)
    print("NEEDS MANUAL REVIEW")


if __name__ == "__main__":
    main()
