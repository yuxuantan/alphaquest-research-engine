"""UI-independent mechanics-review planning and approval services.

The Studio never asks a researcher to copy configuration or data hashes.  This
module derives them through the existing promotion gate, selects a deterministic
risk-based review sample from validation artifacts, and writes the exact
``approval.json`` contract consumed by performance-stage admission.
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal, Mapping

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
import yaml

from alphaquest.dashboard.validation_app import (
    add_review_annotations,
    load_manual_reviews,
    prepare_trade_table,
    trade_id_key,
)
from alphaquest.validation import load_validation_run
from alphaquest.validation.promotion_gate import (
    APPROVAL_SCHEMA,
    REQUIRED_AUTOMATED_CATEGORIES,
    REQUIRED_AUTOMATED_CHECK_NAMES,
    REQUIRED_SAMPLE_CATEGORIES,
    SAMPLING_POLICY_SHA256,
    SAMPLING_POLICY_VERSION,
    inspect_validation_gate,
)


APPROVAL_REVIEW_SCOPE = "implementation_matches_frozen_specification"
FIXED_RANDOM_SAMPLE_SIZE = 5
FIXED_RANDOM_SEED = 0


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
    strategy_implementation_version: int | None = None
    strategy_implementation_sha256: str | None = None
    strategy_certification_manifest_sha256: str | None = None
    fixed_random_sample_size: int = Field(ge=1)
    fixed_random_seed: int
    sampling_policy_version: str
    sampling_policy_sha256: str
    sampled_trade_ids: list[str | int] = Field(default_factory=list)
    sampling_categories: dict[str, list[str | int]] = Field(default_factory=dict)
    sampling_reasons: dict[str, list[str]] = Field(default_factory=dict)
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
        random_sample_size: int | None = None,
        random_seed: int | None = None,
        _gate_report: Mapping[str, Any] | None = None,
    ) -> MechanicsReviewPlan:
        path = Path(config_path).resolve()
        cfg = _load_yaml_mapping(path)
        gate = (
            dict(_gate_report)
            if _gate_report is not None
            else inspect_validation_gate(cfg, path)
        )
        reported_path = gate.get("config_path")
        if reported_path and Path(str(reported_path)).resolve() != path:
            raise ValueError("precomputed mechanics gate belongs to a different config path")
        gate_cfg = ((cfg.get("research_metadata") or {}).get("validation_gate") or {})
        required_size = int(gate_cfg.get("manual_review_random_sample_size", FIXED_RANDOM_SAMPLE_SIZE))
        required_seed = int(gate_cfg.get("manual_review_seed", FIXED_RANDOM_SEED))
        effective_size = required_size if random_sample_size is None else random_sample_size
        effective_seed = required_seed if random_seed is None else random_seed
        if effective_size != required_size or effective_seed != required_seed:
            raise ValueError(
                f"mechanics review sampling is frozen at {required_size} random trades with seed {required_seed}"
            )
        evidence_value = gate.get("evidence_dir")
        approval_value = gate.get("approval_path")
        blockers = _gate_evidence_blockers(gate)
        categories = {name: [] for name in REQUIRED_SAMPLE_CATEGORIES}
        sampling_reasons: dict[str, list[str]] = {}
        sampled: list[str | int] = []
        unreviewed: list[str | int] = []
        non_correct: list[str | int] = []

        if effective_size < 1:
            blockers.append("random_sample_size must be at least one")
        evidence_dir = Path(evidence_value) if evidence_value else None
        if evidence_dir is not None and evidence_dir.is_dir():
            try:
                run = load_validation_run(evidence_dir, include_tick_windows=False)
                reviews = load_manual_reviews(evidence_dir)
                table = prepare_trade_table(run.trades, run.exit_audits, run.validation_checks)
                table = add_review_annotations(table, reviews)
                categories, sampling_reasons, sampling_blockers = _sample_categories(
                    table,
                    run.event_transitions,
                    random_sample_size=effective_size,
                    random_seed=effective_seed,
                    sample_identity="|".join(
                        str(value or "")
                        for value in (
                            gate.get("config_hash"),
                            gate.get("input_data_hash"),
                            gate.get("strategy_implementation_sha256"),
                        )
                    ),
                )
                blockers.extend(sampling_blockers)
                sampled = _ordered_unique(
                    trade_id
                    for category in REQUIRED_SAMPLE_CATEGORIES
                    for trade_id in categories.get(category, [])
                )
                if not sampled:
                    blockers.append("risk-based mechanics sample contains no trades")
                status_by_id = _review_status_by_trade(reviews)
                unreviewed = [trade_id for trade_id in sampled if trade_id_key(trade_id) not in status_by_id]
                non_correct = [
                    trade_id
                    for trade_id in sampled
                    if trade_id_key(trade_id) in status_by_id
                    and status_by_id[trade_id_key(trade_id)].casefold() != "correct"
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
            strategy_implementation_version=gate.get("strategy_implementation_version"),
            strategy_implementation_sha256=gate.get("strategy_implementation_sha256"),
            strategy_certification_manifest_sha256=gate.get(
                "strategy_certification_manifest_sha256"
            ),
            validation_schema_version=gate.get("validation_schema_version"),
            fixed_random_sample_size=effective_size,
            fixed_random_seed=effective_seed,
            sampling_policy_version=SAMPLING_POLICY_VERSION,
            sampling_policy_sha256=SAMPLING_POLICY_SHA256,
            sampled_trade_ids=sampled,
            sampling_categories=categories,
            sampling_reasons=sampling_reasons,
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
        random_sample_size: int | None = None,
        random_seed: int | None = None,
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
        random_sample_size: int | None = None,
        random_seed: int | None = None,
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

    def inspect(
        self,
        config_path: str | Path,
        *,
        precomputed_input_hash: str | None = None,
    ) -> dict[str, Any]:
        path = Path(config_path).resolve()
        return inspect_validation_gate(
            _load_yaml_mapping(path),
            path,
            precomputed_input_hash=precomputed_input_hash,
        )

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
            "sampling_reasons": plan.sampling_reasons,
            "fixed_random_sample_size": plan.fixed_random_sample_size,
            "fixed_random_seed": plan.fixed_random_seed,
            "sampling_policy_version": plan.sampling_policy_version,
            "sampling_policy_sha256": plan.sampling_policy_sha256,
            "parameter_mode": "declared_defaults",
        }
        if plan.strategy_implementation_sha256:
            if (
                plan.strategy_implementation_version is None
                or not plan.strategy_certification_manifest_sha256
            ):
                raise ValueError("certified strategy identity is incomplete")
            payload.update(
                {
                    "strategy_implementation_version": plan.strategy_implementation_version,
                    "strategy_implementation_sha256": plan.strategy_implementation_sha256,
                    "strategy_certification_manifest_sha256": (
                        plan.strategy_certification_manifest_sha256
                    ),
                }
            )
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
    event_transitions: pd.DataFrame,
    *,
    random_sample_size: int,
    random_seed: int,
    sample_identity: str,
) -> tuple[dict[str, list[str | int]], dict[str, list[str]], list[str]]:
    """Select one strategy-agnostic mechanics sample.

    Five hash-ranked trades form the anti-cherry-picking baseline. Additional
    trades are chosen only when needed to cover a universal execution
    lifecycle, one warning code, or one resolved ambiguity. Strategy-specific
    signal semantics belong in automated checks, not handwritten sampler
    branches.
    """

    categories = {name: [] for name in REQUIRED_SAMPLE_CATEGORIES}
    if trades.empty or "trade_id" not in trades.columns:
        return categories, {}, ["canonical trade evidence contains no trade identifiers"]

    transitions_by_trade = _transitions_by_trade(event_transitions)
    records: dict[str, dict[str, Any]] = {}
    missing_direction: list[str] = []
    missing_exit_reason: list[str] = []
    unresolved_ambiguities: list[str] = []

    for _, row in trades.iterrows():
        trade_id = _json_trade_id(row.get("trade_id"))
        key = trade_id_key(trade_id)
        if not key:
            continue
        transitions = transitions_by_trade.get(key, set())
        direction = _canonical_direction(row.get("direction"))
        entry_order = _canonical_entry_order(row.get("entry_order_type")) or "unspecified"
        exit_reason = _text_value(row.get("exit_reason"))
        if direction is None:
            missing_direction.append(str(trade_id))
        if exit_reason is None:
            missing_exit_reason.append(str(trade_id))

        forced_flatten = _is_forced_flatten_trade(row)
        lifecycle = _canonical_exit_lifecycle(
            exit_reason,
            forced_flatten=forced_flatten,
            partial_exit="position_partially_closed" in transitions,
        )
        tags = {
            value
            for value in (
                f"direction:{direction}" if direction else None,
                f"entry_order:{entry_order}" if entry_order else None,
                f"exit_lifecycle:{lifecycle}" if lifecycle else None,
                "order_amendment:bracket" if "bracket_amended" in transitions else None,
                "forced_flatten" if forced_flatten else None,
            )
            if value
        }
        warning_codes = _warning_codes(row)
        if _explicit_false(row.get("engine_exit_matches_path")):
            warning_codes.add("exit_path_mismatch")
        ambiguous = _truthy_value(row.get("same_bar_ambiguous"))
        resolution = _text_value(row.get("ambiguity_resolution"))
        if ambiguous and not resolution:
            unresolved_ambiguities.append(str(trade_id))
        records[key] = {
            "trade_id": trade_id,
            "tags": tags,
            "warnings": warning_codes,
            "ambiguity_resolution": resolution if ambiguous and resolution else None,
            "rank": _sample_rank(
                trade_id,
                random_seed=random_seed,
                sample_identity=sample_identity,
            ),
        }

    ordered = sorted(records, key=lambda key: (records[key]["rank"], key))
    random_keys = ordered[: min(random_sample_size, len(ordered))]
    categories["random_trades"] = [records[key]["trade_id"] for key in random_keys]
    selected = set(random_keys)

    warning_representatives: list[str] = []
    warning_codes = sorted(
        {code for record in records.values() for code in record["warnings"]}
    )
    for code in warning_codes:
        candidates = [key for key in ordered if code in records[key]["warnings"]]
        if candidates:
            representative = candidates[0]
            warning_representatives.append(representative)
            selected.add(representative)
    categories["warning_representatives"] = _record_ids(
        records,
        warning_representatives,
    )

    ambiguity_representatives: list[str] = []
    resolutions = sorted(
        {
            str(record["ambiguity_resolution"])
            for record in records.values()
            if record["ambiguity_resolution"]
        }
    )
    for resolution in resolutions:
        candidates = [
            key
            for key in ordered
            if records[key]["ambiguity_resolution"] == resolution
        ]
        if candidates:
            representative = candidates[0]
            ambiguity_representatives.append(representative)
            selected.add(representative)
    categories["resolved_ambiguities"] = _record_ids(
        records,
        ambiguity_representatives,
    )

    required_tags = {tag for record in records.values() for tag in record["tags"]}
    covered_tags = {
        tag
        for key in selected
        for tag in records[key]["tags"]
    }
    coverage_additions: list[str] = []
    while required_tags - covered_tags:
        uncovered = required_tags - covered_tags
        candidates = [key for key in ordered if key not in selected]
        if not candidates:
            break
        best = min(
            candidates,
            key=lambda key: (
                -len(records[key]["tags"] & uncovered),
                records[key]["rank"],
                key,
            ),
        )
        newly_covered = records[best]["tags"] & uncovered
        if not newly_covered:
            break
        selected.add(best)
        coverage_additions.append(best)
        covered_tags.update(records[best]["tags"])
    categories["universal_coverage"] = _record_ids(records, coverage_additions)

    sampled_keys = _ordered_unique(
        key
        for category in REQUIRED_SAMPLE_CATEGORIES
        for key in (
            trade_id_key(trade_id)
            for trade_id in categories.get(category, [])
        )
        if key in records
    )
    sampling_reasons: dict[str, list[str]] = {}
    for key in sampled_keys:
        reasons = []
        if key in random_keys:
            reasons.append("deterministic random baseline")
        reasons.extend(f"warning:{code}" for code in sorted(records[key]["warnings"]))
        if records[key]["ambiguity_resolution"]:
            reasons.append(
                f"resolved ambiguity:{records[key]['ambiguity_resolution']}"
            )
        reasons.extend(f"covers {tag}" for tag in sorted(records[key]["tags"]))
        sampling_reasons[str(records[key]["trade_id"])] = _ordered_unique_str(reasons)

    blockers = []
    for label, values in (
        ("direction", missing_direction),
        ("exit_reason", missing_exit_reason),
    ):
        if values:
            blockers.append(
                f"canonical mechanics sampling requires {label} for trades: "
                + ", ".join(values)
            )
    if unresolved_ambiguities:
        blockers.append(
            "unresolved stop/target ambiguities must be resolved before manual approval: "
            + ", ".join(unresolved_ambiguities)
        )
    return categories, sampling_reasons, blockers


def _transitions_by_trade(event_transitions: pd.DataFrame) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    if (
        event_transitions.empty
        or "trade_id" not in event_transitions.columns
        or "transition" not in event_transitions.columns
    ):
        return result
    for _, row in event_transitions.dropna(subset=["trade_id"]).iterrows():
        key = trade_id_key(row.get("trade_id"))
        transition = _text_value(row.get("transition"))
        if key and transition:
            result.setdefault(key, set()).add(transition.lower())
    return result


def _sample_rank(
    trade_id: str | int,
    *,
    random_seed: int,
    sample_identity: str,
) -> str:
    payload = (
        f"{SAMPLING_POLICY_VERSION}|{SAMPLING_POLICY_SHA256}|"
        f"{sample_identity}|{random_seed}|{trade_id}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _record_ids(records: Mapping[str, Mapping[str, Any]], keys: list[str]) -> list[str | int]:
    return _ordered_unique(records[key]["trade_id"] for key in keys if key in records)


def _canonical_direction(value: Any) -> str | None:
    text = (_text_value(value) or "").lower()
    if text in {"long", "buy", "1", "+1"}:
        return "long"
    if text in {"short", "sell", "-1"}:
        return "short"
    return None


def _canonical_entry_order(value: Any) -> str | None:
    text = (_text_value(value) or "").lower().replace("-", "_")
    if not text:
        return None
    if "stop" in text:
        return "stop"
    if "limit" in text:
        return "limit"
    if any(token in text for token in ("market", "next_bar", "open", "intrabar")):
        return "market"
    return "other"


def _canonical_exit_lifecycle(
    exit_reason: str | None,
    *,
    forced_flatten: bool,
    partial_exit: bool,
) -> str | None:
    if exit_reason is None:
        return None
    reason = exit_reason.lower()
    if forced_flatten:
        base = "forced_flatten"
    elif "stop" in reason or reason in {"sl", "stop_loss"}:
        base = "stop"
    elif "target" in reason or reason in {"tp", "take_profit"}:
        base = "target"
    elif any(token in reason for token in ("maximum", "holding", "time_exit", "timeout")):
        base = "time_exit"
    else:
        base = "other"
    return f"partial_then_{base}" if partial_exit else base


def _is_forced_flatten_trade(row: pd.Series) -> bool:
    if _truthy_value(row.get("was_forced_flatten")):
        return True
    reason = " ".join(
        value.lower()
        for value in (
            _text_value(row.get("exit_reason")),
            _text_value(row.get("forced_flatten_reason")),
        )
        if value
    )
    return any(
        token in reason
        for token in ("flatten", "session_close", "end_of_day", "eod")
    )


def _warning_codes(row: pd.Series) -> set[str]:
    codes: set[str] = set()
    for item in (_text_value(row.get("check_flags")) or "").split(";"):
        text = item.strip()
        if text.upper().startswith("WARNING:"):
            codes.add(text.split(":", 1)[1].strip() or "validation_warning")
    for item in (_text_value(row.get("warning_flags")) or "").replace(",", ";").split(";"):
        text = item.strip()
        if text and text.lower() not in {"nan", "none", "<na>"}:
            codes.add(text)
    return codes


def _text_value(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text if text and text.lower() not in {"nan", "none", "<na>"} else None


def _truthy_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    try:
        return False if bool(pd.isna(value)) else bool(value)
    except (TypeError, ValueError):
        return False


def _explicit_false(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"0", "false", "no", "n"}
    try:
        return False if bool(pd.isna(value)) else not bool(value)
    except (TypeError, ValueError):
        return False


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
            result[trade_id_key(row.get("trade_id"))] = status
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
