"""Fail-closed mechanics-validation promotion gate.

The gate reads completed validation artifacts and a human approval decision.  It
never calls strategy code, changes a fill, or calculates PnL.  Every performance
campaign must declare ``research_metadata.validation_gate`` and pass it before
the staged runner is allowed to calculate PnL.  Legacy definitions remain
inspectable, but an absent or disabled gate cannot authorize testing.
"""

from __future__ import annotations

from datetime import datetime
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq
import yaml

from alphaquest.data.source import data_source_hash
from alphaquest.research.storage import (
    display_path,
    load_storage_layout,
    resolve_campaign_context,
    resolve_recorded_path,
)
from alphaquest.validation.schema import (
    BAR_WINDOWS_FILENAME,
    EVENT_TRANSITIONS_FILENAME,
    METADATA_FILENAME,
    TRADES_FILENAME,
    VALIDATION_CHECKS_FILENAME,
    VALIDATION_SCHEMA_VERSION,
)
from alphaquest.strategy_certification import StrategyCertificationError, strategy_identity_for_config


APPROVAL_SCHEMA = "alphaquest.validation-approval/v1"
APPROVAL_FILENAME = "approval.json"
FIXED_MANUAL_RANDOM_SAMPLE_SIZE = 5
FIXED_MANUAL_RANDOM_SEED = 0
SUPPORTED_VALIDATION_LANES = {"bar", "event_replay"}
REQUIRED_SAMPLE_CATEGORIES = (
    "first_trade",
    "last_trade",
    "random_trades",
    "best_trade",
    "worst_trade",
    "forced_flattens",
    "same_bar_ambiguity",
    "warnings",
    "strategy_edge_cases",
)
REQUIRED_AUTOMATED_CHECK_NAMES = {
    "metadata_config_hash_present",
    "metadata_input_data_hash_present",
    "validation_lane_declared",
    "source_identity_explicit",
    "execution_costs_and_flatten_explicit",
    "trade_log_count_reconciled",
}
REQUIRED_AUTOMATED_CATEGORIES = {
    "identity",
    "time_ordering",
    "price_logic",
    "filter_logic",
    "exit_logic",
    "data_quality",
    "reconciliation",
}


def validation_gate_config(cfg: dict[str, Any]) -> dict[str, Any] | None:
    research = cfg.get("research_metadata")
    if not isinstance(research, dict):
        return None
    gate = research.get("validation_gate")
    return gate if isinstance(gate, dict) else None


def inspect_validation_gate(
    cfg: dict[str, Any],
    config_path: str | Path,
    *,
    compute_input_hash: bool = True,
    precomputed_input_hash: str | None = None,
) -> dict[str, Any]:
    """Return evidence-backed gate status without mutating repository state."""

    source_path = Path(config_path)
    gate = validation_gate_config(cfg)
    report: dict[str, Any] = {
        "required": True,
        "status": "BLOCKED",
        "verdict": "NEEDS MANUAL REVIEW",
        "errors": [],
        "warnings": [],
        "config_path": str(source_path),
    }
    if not gate:
        report["errors"].append("research_metadata.validation_gate is required before performance testing")
        return report
    if not gate.get("required"):
        report["errors"].append("research_metadata.validation_gate.required must be true")
        return report

    lane = str(gate.get("lane") or "").strip().lower()
    report["lane"] = lane
    if lane not in SUPPORTED_VALIDATION_LANES:
        report["errors"].append(f"validation lane must be one of {sorted(SUPPORTED_VALIDATION_LANES)}")

    evidence_dir = _resolve_path(gate.get("evidence_dir"), source_path)
    approval_path = _resolve_path(gate.get("approval_path"), source_path)
    report["evidence_dir"] = str(evidence_dir) if evidence_dir else None
    report["approval_path"] = str(approval_path) if approval_path else None
    if evidence_dir is None or not evidence_dir.is_dir():
        report["errors"].append("declared validation evidence_dir does not exist")
    if approval_path is None or not approval_path.is_file():
        report["errors"].append("declared manual approval_path does not exist")

    source_hash = _file_sha256(source_path)
    report["config_hash"] = source_hash or None
    input_hash = None
    if precomputed_input_hash is not None:
        input_hash = str(precomputed_input_hash or "") or None
    elif compute_input_hash:
        try:
            subset = gate.get("data_subset") if isinstance(gate.get("data_subset"), dict) else None
            project_root = _storage_project_root(source_path)
            input_hash = data_source_hash(
                _resolved_data_config(cfg.get("data") or {}, project_root),
                subset,
            )
        except (FileNotFoundError, KeyError, OSError, ValueError) as exc:
            report["errors"].append(f"input data hash could not be computed: {exc}")
    else:
        input_hash = str(gate.get("input_data_hash") or "") or None
    report["input_data_hash"] = input_hash

    certification = None
    try:
        certification = strategy_identity_for_config(
            cfg, _storage_project_root(source_path), require_declared_match=True
        )
    except StrategyCertificationError as exc:
        report["errors"].append(f"strategy implementation certification failed: {exc}")
    report["strategy_implementation_version"] = (
        certification.implementation_version if certification else None
    )
    report["strategy_implementation_sha256"] = (
        certification.implementation_sha256 if certification else None
    )
    report["strategy_certification_manifest_sha256"] = (
        certification.manifest_sha256 if certification else None
    )

    metadata = _read_json(evidence_dir / METADATA_FILENAME) if evidence_dir else {}
    approval = _read_json(approval_path) if approval_path else {}
    report["validation_schema_version"] = metadata.get("schema_version")
    report["approval_status"] = approval.get("status")
    report["reviewer"] = approval.get("reviewer")
    report["reviewed_at"] = approval.get("reviewed_at")

    if evidence_dir and evidence_dir.is_dir():
        _validate_lane_artifacts(evidence_dir, lane, metadata, report["errors"])
        _validate_automated_checks(evidence_dir, report["errors"])
    _validate_metadata(metadata, lane, source_hash, input_hash, certification, report["errors"])
    _validate_approval(approval, lane, source_hash, input_hash, metadata, certification, report["errors"])
    if gate.get("manual_review_random_sample_size") is not None:
        expected_size = int(gate.get("manual_review_random_sample_size"))
        expected_seed = int(gate.get("manual_review_seed", FIXED_MANUAL_RANDOM_SEED))
        if approval.get("fixed_random_sample_size") != expected_size:
            report["errors"].append(f"manual approval must use the fixed {expected_size}-trade random sample")
        if approval.get("fixed_random_seed") != expected_seed:
            report["errors"].append(f"manual approval must use fixed random seed {expected_seed}")
        if approval.get("parameter_mode") != str(gate.get("parameter_mode") or "declared_defaults"):
            report["errors"].append("manual approval must use the variant's declared default parameters")

    if not report["errors"]:
        report["status"] = "APPROVED_FOR_TESTING"
        report["verdict"] = "PASS"
    elif approval and str(approval.get("status") or "").lower() == "rejected":
        report["status"] = "REJECTED"
        report["verdict"] = "FAIL"
    return report


def require_validation_approval(cfg: dict[str, Any], config_path: str | Path) -> dict[str, Any]:
    """Require a current, hash-bound manual mechanics approval before PnL tests."""

    report = inspect_validation_gate(cfg, config_path)
    if report["status"] != "APPROVED_FOR_TESTING":
        details = "\n- ".join(report["errors"] or report["warnings"] or ["approval is unresolved"])
        raise ValueError(f"Mechanics validation promotion gate failed:\n- {details}")
    return report


def require_prior_variant_approvals(cfg: dict[str, Any], config_path: str | Path) -> None:
    """Require approved mechanics and a hash-bound FAIL before a later variant runs."""

    path = Path(config_path).resolve()
    project_root = _storage_project_root(path)
    context = resolve_campaign_context(path, project_root=project_root)
    if context is None or context.campaign_id != str(cfg.get("campaign_id") or ""):
        return
    campaign_root = context.campaign_root
    campaign_path = campaign_root / "campaign.yaml"
    if not campaign_path.is_file():
        return
    try:
        campaign = yaml.safe_load(campaign_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return
    contract_version = int(campaign.get("governance_contract_version") or 0)
    if contract_version < 2:
        return
    variants = [str(item) for item in campaign.get("variants") or []]
    current = str(cfg.get("variant_id") or "")
    if current not in variants:
        raise ValueError("Campaign sequencing gate failed: current variant is not in campaign.yaml variants")
    unresolved = []
    try:
        relative = path.relative_to(campaign_root)
    except ValueError:
        raise ValueError("Campaign sequencing gate failed: config is outside its resolved campaign root")
    parts = relative.parts
    if len(parts) >= 4 and parts[0] == "follow_up_attempts" and parts[-1] == "config.yaml":
        prior_root = campaign_root / "follow_up_attempts" / parts[1]
    elif len(parts) >= 3 and parts[0] == "variants" and parts[-1] == "config.yaml":
        prior_root = campaign_root / "variants"
    else:
        raise ValueError("Campaign sequencing gate failed: config does not belong to a governed attempt layout")
    for prior_variant in variants[: variants.index(current)]:
        prior_path = prior_root / prior_variant / "config.yaml"
        try:
            prior_cfg = yaml.safe_load(prior_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            unresolved.append(f"{prior_variant}: config unavailable ({exc})")
            continue
        report = inspect_validation_gate(prior_cfg, prior_path)
        if report["status"] != "APPROVED_FOR_TESTING":
            unresolved.append(f"{prior_variant}: {report['status']}")
    if contract_version >= 3 and variants.index(current) > 0:
        history = campaign.get("sequential_variant_history")
        expected = variants.index(current)
        if not isinstance(history, list) or len(history) < expected:
            unresolved.append("failure-informed sequential lineage is missing")
        else:
            lineage = history[expected - 1]
            if not isinstance(lineage, dict):
                unresolved.append("failure-informed sequential lineage is invalid")
            elif (
                str(lineage.get("variant_id") or "") != current
                or str(lineage.get("predecessor_variant_id") or "") != variants[expected - 1]
                or str(lineage.get("predecessor_verdict") or "") != "FAIL"
            ):
                unresolved.append("failure-informed sequential lineage does not match campaign order")
            else:
                result_path = _resolve_path(lineage.get("predecessor_result_path"), path)
                expected_hash = str(lineage.get("predecessor_result_sha256") or "")
                actual_hash = _file_sha256(result_path) if result_path else None
                result = _read_json(result_path) if result_path else {}
                verdict = str(result.get("verdict") or result.get("research_verdict") or result.get("decision") or "")
                if not result_path or not result_path.is_file():
                    unresolved.append("predecessor FAIL result artifact is missing")
                elif actual_hash != expected_hash:
                    unresolved.append("predecessor FAIL result artifact hash has drifted")
                elif verdict != "FAIL":
                    unresolved.append(f"predecessor terminal verdict is {verdict or 'unresolved'}, not FAIL")
    if unresolved:
        raise ValueError(
            "Campaign sequencing gate failed; prior variants require completed mechanics approval:\n- "
            + "\n- ".join(unresolved)
        )


def _validate_lane_artifacts(evidence_dir: Path, lane: str, metadata: dict[str, Any], errors: list[str]) -> None:
    if not metadata:
        errors.append(f"{METADATA_FILENAME} is missing or invalid")
    checks_path = evidence_dir / VALIDATION_CHECKS_FILENAME
    if not checks_path.is_file():
        errors.append(f"{VALIDATION_CHECKS_FILENAME} is missing")
    trades_path = evidence_dir / TRADES_FILENAME
    if not trades_path.is_file():
        errors.append(f"{TRADES_FILENAME} is missing")
    else:
        try:
            if pq.ParquetFile(trades_path).metadata.num_rows == 0:
                errors.append(f"{TRADES_FILENAME} contains no validation trades")
        except (OSError, ValueError) as exc:
            errors.append(f"{TRADES_FILENAME} could not be read: {exc}")
    lane_file = EVENT_TRANSITIONS_FILENAME if lane == "event_replay" else BAR_WINDOWS_FILENAME
    path = evidence_dir / lane_file
    if not path.is_file():
        errors.append(f"{lane} validation requires {lane_file}")
        return
    try:
        if pq.ParquetFile(path).metadata.num_rows == 0:
            errors.append(f"{lane_file} contains no validation rows")
    except (OSError, ValueError) as exc:
        errors.append(f"{lane_file} could not be read: {exc}")


def _validate_automated_checks(evidence_dir: Path, errors: list[str]) -> None:
    path = evidence_dir / VALIDATION_CHECKS_FILENAME
    if not path.is_file():
        return
    try:
        checks = pd.read_parquet(path)
    except (OSError, ValueError) as exc:
        errors.append(f"{VALIDATION_CHECKS_FILENAME} could not be read: {exc}")
        return
    if checks.empty:
        errors.append("automated validation checks are empty")
        return
    status = checks.get("status", pd.Series("", index=checks.index)).astype(str).str.lower()
    severity = checks.get("severity", pd.Series("", index=checks.index)).astype(str).str.lower()
    passing = status.isin({"pass", "passed", "ok"})
    unresolved = checks[
        status.isin({"fail", "failed", "error", "unresolved"}) | (severity.eq("error") & ~passing)
    ]
    if not unresolved.empty:
        errors.append(f"automated validation has {len(unresolved)} unresolved error(s)")
    names = set(checks.get("check_name", pd.Series(dtype=str)).dropna().astype(str))
    missing_names = sorted(REQUIRED_AUTOMATED_CHECK_NAMES - names)
    if missing_names:
        errors.append(f"automated validation is missing required checks: {', '.join(missing_names)}")
    categories = set(checks.get("category", pd.Series(dtype=str)).dropna().astype(str))
    missing_categories = sorted(REQUIRED_AUTOMATED_CATEGORIES - categories)
    if missing_categories:
        errors.append(f"automated validation is missing required categories: {', '.join(missing_categories)}")


def _validate_metadata(
    metadata: dict[str, Any],
    lane: str,
    config_hash: str,
    input_hash: str | None,
    certification: Any,
    errors: list[str],
) -> None:
    if not metadata:
        return
    if str(metadata.get("schema_version") or "") != VALIDATION_SCHEMA_VERSION:
        errors.append("validation metadata schema version is stale or unsupported")
    if str(metadata.get("validation_lane") or "").lower() != lane:
        errors.append("validation metadata lane does not match the declared gate lane")
    if str(metadata.get("config_hash") or "") != config_hash:
        errors.append("validation metadata config hash does not match the authored config")
    if not input_hash or str(metadata.get("input_data_hash") or "") != input_hash:
        errors.append("validation metadata input-data hash does not match the declared data")
    if certification is not None:
        if metadata.get("strategy_implementation_version") != certification.implementation_version:
            errors.append("validation metadata strategy implementation version is stale or mismatched")
        if str(metadata.get("strategy_implementation_sha256") or "") != certification.implementation_sha256:
            errors.append("validation metadata strategy implementation hash is stale or mismatched")
        if (
            str(metadata.get("strategy_certification_manifest_sha256") or "")
            != certification.manifest_sha256
        ):
            errors.append("validation metadata strategy certification manifest hash is stale or mismatched")


def _validate_approval(
    approval: dict[str, Any],
    lane: str,
    config_hash: str,
    input_hash: str | None,
    metadata: dict[str, Any],
    certification: Any,
    errors: list[str],
) -> None:
    if not approval:
        return
    if approval.get("schema") != APPROVAL_SCHEMA:
        errors.append("manual approval schema is missing or unsupported")
    if str(approval.get("status") or "").lower() != "approved_for_testing":
        errors.append("manual approval status is not approved_for_testing")
    if not str(approval.get("reviewer") or "").strip():
        errors.append("manual approval reviewer is missing")
    if not _aware_timestamp(approval.get("reviewed_at")):
        errors.append("manual approval reviewed_at must be timezone-aware")
    if not str(approval.get("notes") or "").strip():
        errors.append("manual approval notes are missing")
    if str(approval.get("lane") or "").lower() != lane:
        errors.append("manual approval lane does not match validation evidence")
    if str(approval.get("config_hash") or "") != config_hash:
        errors.append("manual approval config hash is stale or mismatched")
    if not input_hash or str(approval.get("input_data_hash") or "") != input_hash:
        errors.append("manual approval input-data hash is stale or mismatched")
    schema_version = str(metadata.get("schema_version") or "")
    if str(approval.get("validation_schema_version") or "") != schema_version:
        errors.append("manual approval validation schema version is stale or mismatched")
    if certification is not None:
        if approval.get("strategy_implementation_version") != certification.implementation_version:
            errors.append("manual approval strategy implementation version is stale or mismatched")
        if str(approval.get("strategy_implementation_sha256") or "") != certification.implementation_sha256:
            errors.append("manual approval strategy implementation hash is stale or mismatched")
        if (
            str(approval.get("strategy_certification_manifest_sha256") or "")
            != certification.manifest_sha256
        ):
            errors.append("manual approval strategy certification manifest hash is stale or mismatched")
    trade_ids = approval.get("sampled_trade_ids")
    if not isinstance(trade_ids, list) or not trade_ids:
        errors.append("manual approval must list sampled_trade_ids")
    categories = approval.get("sampling_categories")
    if not isinstance(categories, dict):
        errors.append("manual approval sampling_categories must be a mapping")
    else:
        missing = [name for name in REQUIRED_SAMPLE_CATEGORIES if name not in categories]
        if missing:
            errors.append(f"manual approval is missing sampling categories: {', '.join(missing)}")


def _resolve_path(value: Any, config_path: Path) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    if path.is_absolute():
        return path
    project_root = _storage_project_root(config_path)
    layout = load_storage_layout(project_root)
    configured_roots = (
        *layout.campaign_roots,
        *layout.evidence_roots,
        layout.research_artifact_root,
        layout.catalog_root,
        layout.views_root,
        layout.run_store_root,
        layout.draft_root,
        layout.dataset_root,
        layout.handoff_root,
        layout.studio_runtime_root,
    )
    text = path.as_posix()
    for root in configured_roots:
        recorded = display_path(root, project_root)
        recorded_path = Path(recorded)
        if recorded_path.is_absolute():
            continue
        prefix = recorded_path.as_posix().rstrip("/")
        if text == prefix or text.startswith(prefix + "/"):
            return project_root / path
    project_path = resolve_recorded_path(path, project_root=project_root, layout=layout)
    if project_path.exists() or text.startswith(("campaigns/", "backtest-campaigns/", "examples/")):
        return project_path
    return config_path.parent / path


def _storage_project_root(config_path: Path) -> Path:
    resolved = config_path.resolve()
    for parent in (resolved.parent, *resolved.parents):
        if (parent / "config" / "storage_layout.yaml").is_file():
            return parent
    for parent in (resolved.parent, *resolved.parents):
        for campaign_root in (
            parent / "research" / "campaigns" / "active",
            parent / "research" / "campaigns" / "archive",
        ):
            try:
                resolved.relative_to(campaign_root)
            except ValueError:
                continue
            return parent
    for parent in (resolved.parent, *resolved.parents):
        if parent.name == "research":
            continue
        try:
            resolved.relative_to(parent / "campaigns")
        except ValueError:
            continue
        return parent
    return Path.cwd().resolve()


def _resolved_data_config(data_config: dict[str, Any], project_root: Path) -> dict[str, Any]:
    """Resolve recorded local inputs for hashing without mutating the config contract."""

    resolved = deepcopy(data_config)
    path_keys = {
        "raw_csv",
        "raw_parquet",
        "raw_dir",
        "roll_calendar",
        "archive",
        "contract_manifest",
        "quality_manifest",
        "raw_manifest",
        "session_levels",
        "concordance_report",
    }

    def visit(value: Any) -> None:
        if not isinstance(value, dict):
            return
        for key, item in tuple(value.items()):
            if key in path_keys and isinstance(item, str) and item:
                path = Path(item)
                if not path.is_absolute():
                    value[key] = str(project_root / path)
            elif isinstance(item, dict):
                visit(item)

    visit(resolved)
    return resolved


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _aware_timestamp(value: Any) -> bool:
    if not value:
        return False
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    return timestamp.tzinfo is not None
