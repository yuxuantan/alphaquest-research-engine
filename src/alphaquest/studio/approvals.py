"""UI-independent mechanics-review planning and approval services.

The Studio never asks a researcher to copy configuration or data hashes.  This
module derives them through the existing promotion gate, selects a deterministic
risk-based review sample from validation artifacts, and writes the exact
``approval.json`` contract consumed by performance-stage admission.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
import yaml

from alphaquest.dashboard.validation_app import (
    add_review_annotations,
    build_review_queue,
    load_manual_reviews,
    prepare_trade_table,
)
from alphaquest.validation import load_validation_run
from alphaquest.validation.promotion_gate import (
    APPROVAL_SCHEMA,
    REQUIRED_AUTOMATED_CATEGORIES,
    REQUIRED_AUTOMATED_CHECK_NAMES,
    REQUIRED_SAMPLE_CATEGORIES,
    inspect_validation_gate,
)


APPROVAL_REVIEW_SCOPE = "implementation_matches_frozen_specification"

_CATEGORY_MODES: tuple[tuple[str, str, int | None], ...] = (
    ("first_trade", "First 20 trades chronologically", 1),
    ("last_trade", "Last 20 trades chronologically", 1),
    ("random_trades", "Random 20 trades", None),
    ("best_trade", "Best 20 trades by R", 1),
    ("worst_trade", "Worst 20 trades by R", 1),
    ("forced_flattens", "All forced-flatten trades", None),
    ("same_bar_ambiguity", "All same-bar ambiguous trades", None),
    ("warnings", "All trades with mismatch warnings", None),
    ("strategy_edge_cases", "High-impact edge cases", None),
)


class MechanicsReviewPlan(BaseModel):
    """Deterministic review requirements for one frozen variant."""

    model_config = ConfigDict(extra="forbid")

    config_path: str
    evidence_dir: str | None
    approval_path: str | None
    lane: str | None
    config_hash: str | None
    input_data_hash: str | None
    validation_schema_version: str | None
    sampled_trade_ids: list[str | int] = Field(default_factory=list)
    sampling_categories: dict[str, list[str | int]] = Field(default_factory=dict)
    unreviewed_trade_ids: list[str | int] = Field(default_factory=list)
    non_correct_trade_ids: list[str | int] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)

    @property
    def ready_for_approval(self) -> bool:
        return not self.blockers and not self.unreviewed_trade_ids and not self.non_correct_trade_ids


class MechanicsApprovalService:
    """Plan, approve, reject, and inspect mechanics-validation decisions."""

    def plan(
        self,
        config_path: str | Path,
        *,
        random_sample_size: int = 5,
        random_seed: int = 0,
    ) -> MechanicsReviewPlan:
        path = Path(config_path).resolve()
        cfg = _load_yaml_mapping(path)
        gate = inspect_validation_gate(cfg, path)
        evidence_value = gate.get("evidence_dir")
        approval_value = gate.get("approval_path")
        blockers = _gate_evidence_blockers(gate)
        categories = {name: [] for name in REQUIRED_SAMPLE_CATEGORIES}
        sampled: list[str | int] = []
        unreviewed: list[str | int] = []
        non_correct: list[str | int] = []

        if random_sample_size < 1:
            blockers.append("random_sample_size must be at least one")
        evidence_dir = Path(evidence_value) if evidence_value else None
        if evidence_dir is not None and evidence_dir.is_dir():
            try:
                run = load_validation_run(evidence_dir, include_tick_windows=False)
                reviews = load_manual_reviews(evidence_dir)
                table = prepare_trade_table(run.trades, run.exit_audits, run.validation_checks)
                table = add_review_annotations(table, reviews)
                categories = _sample_categories(
                    table,
                    run.condition_snapshots,
                    run.exit_audits,
                    run.bar_windows,
                    random_sample_size=random_sample_size,
                    random_seed=random_seed,
                    tick_size=_float_or_none(run.metadata.get("tick_size")),
                )
                sampled = _ordered_unique(
                    trade_id
                    for category in REQUIRED_SAMPLE_CATEGORIES
                    for trade_id in categories.get(category, [])
                )
                if not sampled:
                    blockers.append("risk-based mechanics sample contains no trades")
                status_by_id = _review_status_by_trade(reviews)
                unreviewed = [trade_id for trade_id in sampled if str(trade_id) not in status_by_id]
                non_correct = [
                    trade_id
                    for trade_id in sampled
                    if str(trade_id) in status_by_id and status_by_id[str(trade_id)].casefold() != "correct"
                ]
                blockers.extend(_automated_check_blockers(run.validation_checks))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                blockers.append(f"validation evidence could not be prepared for review: {exc}")

        return MechanicsReviewPlan(
            config_path=str(path),
            evidence_dir=evidence_value,
            approval_path=approval_value,
            lane=gate.get("lane"),
            config_hash=gate.get("config_hash"),
            input_data_hash=gate.get("input_data_hash"),
            validation_schema_version=gate.get("validation_schema_version"),
            sampled_trade_ids=sampled,
            sampling_categories=categories,
            unreviewed_trade_ids=unreviewed,
            non_correct_trade_ids=non_correct,
            blockers=_ordered_unique_str(blockers),
        )

    def approve(
        self,
        config_path: str | Path,
        *,
        reviewer: str,
        notes: str,
        reviewed_at: datetime | str | None = None,
        random_sample_size: int = 5,
        random_seed: int = 0,
    ) -> dict[str, Any]:
        """Write a hash-bound approval only after every selected trade is correct."""

        plan = self.plan(
            config_path,
            random_sample_size=random_sample_size,
            random_seed=random_seed,
        )
        if plan.blockers:
            raise ValueError("Mechanics approval is blocked:\n- " + "\n- ".join(plan.blockers))
        if plan.unreviewed_trade_ids:
            raise ValueError(
                "Mechanics approval is blocked; sampled trades remain unreviewed: "
                + ", ".join(map(str, plan.unreviewed_trade_ids))
            )
        if plan.non_correct_trade_ids:
            raise ValueError(
                "Mechanics approval is blocked; sampled trades are not marked Correct: "
                + ", ".join(map(str, plan.non_correct_trade_ids))
            )
        return self._write_decision(
            plan,
            status="approved_for_testing",
            reviewer=reviewer,
            notes=notes,
            reviewed_at=reviewed_at,
            verify_pass=True,
        )

    def reject(
        self,
        config_path: str | Path,
        *,
        reviewer: str,
        notes: str,
        reviewed_at: datetime | str | None = None,
        random_sample_size: int = 5,
        random_seed: int = 0,
    ) -> dict[str, Any]:
        """Persist an evidence-bound mechanics rejection without running PnL."""

        plan = self.plan(
            config_path,
            random_sample_size=random_sample_size,
            random_seed=random_seed,
        )
        fatal = [item for item in plan.blockers if "approval_path" not in item]
        if fatal:
            raise ValueError("Mechanics rejection is blocked:\n- " + "\n- ".join(fatal))
        return self._write_decision(
            plan,
            status="rejected",
            reviewer=reviewer,
            notes=notes,
            reviewed_at=reviewed_at,
            verify_pass=False,
        )

    def inspect(self, config_path: str | Path) -> dict[str, Any]:
        path = Path(config_path).resolve()
        return inspect_validation_gate(_load_yaml_mapping(path), path)

    def _write_decision(
        self,
        plan: MechanicsReviewPlan,
        *,
        status: Literal["approved_for_testing", "rejected"],
        reviewer: str,
        notes: str,
        reviewed_at: datetime | str | None,
        verify_pass: bool,
    ) -> dict[str, Any]:
        reviewer_value = reviewer.strip()
        notes_value = notes.strip()
        if not reviewer_value:
            raise ValueError("reviewer is required")
        if not notes_value:
            raise ValueError("review notes are required")
        timestamp = _aware_iso(reviewed_at)
        if not plan.approval_path:
            raise ValueError("validation gate does not declare an approval_path")
        if not plan.lane or not plan.config_hash or not plan.input_data_hash or not plan.validation_schema_version:
            raise ValueError("validation evidence is not fully hash- and schema-bound")
        if not plan.sampled_trade_ids:
            raise ValueError("at least one sampled trade is required")

        payload: dict[str, Any] = {
            "schema": APPROVAL_SCHEMA,
            "status": status,
            "reviewer": reviewer_value,
            "reviewed_at": timestamp,
            "notes": notes_value,
            "review_scope": APPROVAL_REVIEW_SCOPE,
            "profitability_approval": False,
            "lane": plan.lane,
            "config_hash": plan.config_hash,
            "input_data_hash": plan.input_data_hash,
            "validation_schema_version": plan.validation_schema_version,
            "sampled_trade_ids": plan.sampled_trade_ids,
            "sampling_categories": plan.sampling_categories,
        }
        approval_path = Path(plan.approval_path)
        previous = approval_path.read_bytes() if approval_path.is_file() else None
        _atomic_write_json(approval_path, payload)
        report = self.inspect(plan.config_path)
        expected = "APPROVED_FOR_TESTING" if verify_pass else "REJECTED"
        if report.get("status") != expected:
            if previous is None:
                approval_path.unlink(missing_ok=True)
            else:
                _atomic_write_bytes(approval_path, previous)
            raise ValueError(
                f"promotion gate rejected the generated mechanics decision ({report.get('status')}): "
                + "; ".join(report.get("errors") or ["unknown gate error"])
            )
        return payload


def require_all_variant_mechanics_approved(config_paths: list[str | Path]) -> list[dict[str, Any]]:
    """Fail unless every frozen variant has a current mechanics approval."""

    service = MechanicsApprovalService()
    reports = [service.inspect(path) for path in config_paths]
    unresolved = [
        f"{Path(report['config_path']).parent.name}: {report.get('status')}"
        for report in reports
        if report.get("status") != "APPROVED_FOR_TESTING"
    ]
    if unresolved:
        raise ValueError("All variants require mechanics approval before performance testing:\n- " + "\n- ".join(unresolved))
    return reports


def _sample_categories(
    trades: pd.DataFrame,
    conditions: pd.DataFrame,
    exit_audits: pd.DataFrame,
    bar_windows: pd.DataFrame,
    *,
    random_sample_size: int,
    random_seed: int,
    tick_size: float | None,
) -> dict[str, list[str | int]]:
    categories: dict[str, list[str | int]] = {}
    for category, mode, fixed_size in _CATEGORY_MODES:
        size = fixed_size if fixed_size is not None else random_sample_size
        queue = build_review_queue(
            trades,
            conditions,
            exit_audits,
            bar_windows,
            sample_mode=mode,
            sample_size=size,
            random_seed=random_seed,
            tick_size=tick_size,
        )
        ids = queue.get("trade_id", pd.Series(dtype="object")).tolist()
        categories[category] = _ordered_unique(_json_trade_id(item) for item in ids)
    return categories


def _automated_check_blockers(checks: pd.DataFrame) -> list[str]:
    if checks.empty:
        return ["automated validation checks are empty"]
    status = checks.get("status", pd.Series("", index=checks.index)).fillna("").astype(str).str.lower()
    severity = checks.get("severity", pd.Series("", index=checks.index)).fillna("").astype(str).str.lower()
    passing = status.isin({"pass", "passed", "ok"})
    unresolved = status.isin({"fail", "failed", "error", "unresolved"}) | (severity.eq("error") & ~passing)
    blockers = []
    if bool(unresolved.any()):
        blockers.append(f"automated validation has {int(unresolved.sum())} unresolved error(s)")
    names = set(checks.get("check_name", pd.Series(dtype=str)).dropna().astype(str))
    missing_names = sorted(REQUIRED_AUTOMATED_CHECK_NAMES - names)
    if missing_names:
        blockers.append("automated validation is missing required checks: " + ", ".join(missing_names))
    categories = set(checks.get("category", pd.Series(dtype=str)).dropna().astype(str))
    missing_categories = sorted(REQUIRED_AUTOMATED_CATEGORIES - categories)
    if missing_categories:
        blockers.append("automated validation is missing required categories: " + ", ".join(missing_categories))
    return blockers


def _gate_evidence_blockers(report: dict[str, Any]) -> list[str]:
    blockers = []
    if not report.get("required"):
        blockers.append("mechanics validation gate is not required by the authored config")
    for error in report.get("errors") or []:
        # Missing/stale approval is what this service is intended to resolve.
        if error == "declared manual approval_path does not exist" or error.startswith("manual approval "):
            continue
        blockers.append(str(error))
    return blockers


def _review_status_by_trade(reviews: pd.DataFrame) -> dict[str, str]:
    if reviews.empty or "trade_id" not in reviews.columns or "reviewer_status" not in reviews.columns:
        return {}
    result = {}
    for _, row in reviews.iterrows():
        status = str(row.get("reviewer_status") or "").strip()
        if status:
            result[str(row.get("trade_id"))] = status
    return result


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"could not read config {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"config must contain a YAML mapping: {path}")
    return value


def _aware_iso(value: datetime | str | None) -> str:
    if value is None:
        parsed = datetime.now(UTC)
    elif isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("reviewed_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("reviewed_at must be timezone-aware")
    return parsed.isoformat()


def _json_trade_id(value: Any) -> str | int:
    if pd.isna(value):
        raise ValueError("sampled trade_id cannot be missing")
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return value
    if hasattr(value, "item"):
        value = value.item()
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return str(value)


def _ordered_unique(values: Any) -> list[Any]:
    seen: set[tuple[type, str]] = set()
    result = []
    for value in values:
        key = (type(value), str(value))
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _ordered_unique_str(values: list[str]) -> list[str]:
    return [str(item) for item in _ordered_unique(str(value) for value in values)]


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    data = (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    _atomic_write_bytes(path, data)


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
