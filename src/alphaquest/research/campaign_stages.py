from __future__ import annotations

import copy
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import time
from typing import Any

import pandas as pd
import yaml

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.backtest.equity_report import write_equity_report
from alphaquest.backtest.metrics import calculate_metrics
from alphaquest.data.pipeline import prepare_data
from alphaquest.data.source import data_source_hash
from alphaquest.prop.rules import PropRules
from alphaquest.research.core_grid import run_core_grid
from alphaquest.research.execution import run_research_backtest
from alphaquest.research.monkey import run_monkey
from alphaquest.research.monte_carlo import run_monte_carlo, run_monte_carlo_with_audit
from alphaquest.research.policy import active_research_policy_metadata, load_research_policy
from alphaquest.research.preflight import run_preflight
from alphaquest.research.run_store import ensure_run_uid
from alphaquest.research.schemas import (
    validate_campaign_config_contract,
    validate_run_summary_contract,
    validate_stage_result_contract,
)
from alphaquest.research.wfa import run_wfa
from alphaquest.research.storage import resolve_campaign_context
from alphaquest.utils.config import (
    CAMPAIGN_REPORT_ROOT,
    CAMPAIGN_CONFIG_FILENAME,
    SOURCE_CONFIG_SNAPSHOT_FILENAME,
    VARIANT_TEST_SUMMARY_FILENAME,
    campaign_test_run_id,
    campaign_metadata_info,
    config_timeframe,
    ensure_variant_metadata,
    load_yaml,
    update_runs_index,
    validate_campaign_run_root,
    variant_root,
    write_json,
)
from alphaquest.utils.hashing import file_sha256, object_sha256
from alphaquest.utils.params import apply_dotted_params
from alphaquest.utils.reports import market_timezone, write_report_csv
from alphaquest.validation.promotion_gate import require_prior_variant_approvals, require_validation_approval
from alphaquest.version import ENGINE_CONTRACT_VERSION


_RESEARCH_POLICY = load_research_policy()
ACCEPTANCE_STAGE = _RESEARCH_POLICY.acceptance_stage
PRE_ACCEPTANCE_STAGE_ORDER = list(_RESEARCH_POLICY.pre_acceptance_stage_order)
DEFAULT_STAGE_ORDER = list(_RESEARCH_POLICY.stage_order)

TRADE_PATH_STRESS_SKIP_REASON = (
    "trade-path stress is globally disabled for campaign stages; "
    "monkey gates use random-entry core-beat rates"
)

DEFAULT_STAGE_CRITERIA = copy.deepcopy(_RESEARCH_POLICY.stage_criteria)
DEFAULT_SHORTLIST_DATA_WINDOW = copy.deepcopy(_RESEARCH_POLICY.shortlist_data_window)
DEFAULT_WFA_DATA_WINDOW = copy.deepcopy(_RESEARCH_POLICY.wfa_data_window)
DEFAULT_MONKEY_RUNS = _RESEARCH_POLICY.monkey_runs
MONKEY_STAGE_NAMES = {
    "limited_monkey_test",
    "wfa_oos_monkey_test",
    "simulated_incubation_monkey",
}

LIMITED_CORE_GRID_BENCHMARK_KEYS = {
    "min_total_net_profit",
    "max_drawdown",
    "max_drawdown_pct",
    "min_trades_per_year",
    "max_consecutive_losses",
    "min_trade_count",
    "preferred_min_total_trades",
    "max_best_day_concentration",
}

STAGE_LABELS = {
    "limited_core_grid_test": "Limited Core Grid Test",
    "limited_monkey_test": "Limited Monkey Test",
    "walk_forward_analysis": "Walk Forward Analysis (WFA)",
    "wfa_oos_monkey_test": "WFA OOS Monkey Test",
    "wfa_oos_monte_carlo": "WFA OOS Monte Carlo",
    "simulated_incubation_core": "Simulated Incubation (OOS) Core",
    "simulated_incubation_monkey": "Simulated Incubation (OOS) Monkey",
    ACCEPTANCE_STAGE: "Acceptance OOS Test",
}

REQUIRED_MECHANICS_REVIEW_FIELDS = (
    "mechanic_expresses_edge",
    "entry_logic_rationale",
    "stop_loss_rationale",
    "target_exit_rationale",
    "profitability_rationale",
    "known_failure_modes",
)
MECHANICS_REVIEW_MIN_CHARS = 80


def canonicalize_campaign_config(cfg: dict, *, include_acceptance: bool = True) -> dict:
    out = copy.deepcopy(cfg)
    policy_metadata = active_research_policy_metadata()
    out["research_policy"] = policy_metadata
    out.setdefault("monkey", {})["runs"] = DEFAULT_MONKEY_RUNS
    campaign_tests = copy.deepcopy(out.get("campaign_tests") or {})
    incubation_declared = campaign_tests.get("simulated_incubation_core") or {}
    acceptance_declared = campaign_tests.get(ACCEPTANCE_STAGE) or {}
    incubation_test_months = int(
        incubation_declared.get(
            "test_months",
            _RESEARCH_POLICY.simulated_incubation.get("test_months", 12),
        )
    )
    acceptance_test_months = int(
        acceptance_declared.get(
            "test_months",
            _RESEARCH_POLICY.acceptance_oos.get("test_months", 6),
        )
    )
    stage_order = DEFAULT_STAGE_ORDER if include_acceptance else PRE_ACCEPTANCE_STAGE_ORDER
    campaign_tests["stage_order"] = list(stage_order)
    campaign_tests["research_policy"] = policy_metadata
    for stage_name in DEFAULT_STAGE_ORDER:
        stage_cfg = copy.deepcopy(campaign_tests.get(stage_name) or {})
        stage_cfg.pop("enabled", None)
        stage_cfg["criteria"] = copy.deepcopy(DEFAULT_STAGE_CRITERIA[stage_name])
        if stage_name in {"limited_core_grid_test", "limited_monkey_test"}:
            stage_cfg.pop("data_subset", None)
            stage_cfg["data_window"] = copy.deepcopy(DEFAULT_SHORTLIST_DATA_WINDOW)
        if stage_name in MONKEY_STAGE_NAMES:
            stage_cfg["runs"] = DEFAULT_MONKEY_RUNS
        if stage_name == "walk_forward_analysis":
            stage_cfg.pop("data_subset", None)
            stage_cfg["data_window"] = copy.deepcopy(DEFAULT_WFA_DATA_WINDOW)
            if stage_cfg["data_window"].get("mode") == "before_sequential_holdouts":
                stage_cfg["data_window"].update(
                    {
                        "incubation_test_months": incubation_test_months,
                        "acceptance_test_months": acceptance_test_months,
                    }
                )
        if stage_name == "simulated_incubation_core":
            stage_cfg.setdefault("train_months", int(_RESEARCH_POLICY.simulated_incubation.get("train_months", 48)))
            stage_cfg.setdefault("test_months", int(_RESEARCH_POLICY.simulated_incubation.get("test_months", 12)))
            stage_cfg["holdout_after_test_months"] = acceptance_test_months
        if stage_name == ACCEPTANCE_STAGE:
            stage_cfg.setdefault("train_months", int(_RESEARCH_POLICY.acceptance_oos.get("train_months", 24)))
            stage_cfg.setdefault("test_months", int(_RESEARCH_POLICY.acceptance_oos.get("test_months", 6)))
            if not include_acceptance:
                stage_cfg["enabled"] = False
        campaign_tests[stage_name] = stage_cfg
    out["campaign_tests"] = campaign_tests
    return out


def campaign_test_data_window_plan(cfg: dict) -> list[dict[str, Any]]:
    """Return the pre-PnL stage windows that Studio can present for review."""

    canonical = canonicalize_campaign_config(cfg)
    campaign_tests = canonical.get("campaign_tests") or {}
    rows: list[dict[str, Any]] = []
    gate = ((canonical.get("research_metadata") or {}).get("validation_gate") or {})
    mechanics_subset = gate.get("data_subset") if isinstance(gate.get("data_subset"), dict) else {}
    rows.append(
        _planned_window_row(
            "mechanics_validation",
            "Mechanics Validation",
            mechanics_subset,
            input_kind="market_sessions",
            detail="Frozen defaults; manually reconciled sample before every PnL-bearing stage.",
        )
    )

    limited_core = _stage_subset(
        canonical,
        campaign_tests.get("limited_core_grid_test") or {},
        "core_grid",
    )
    rows.append(
        _planned_window_row(
            "limited_core_grid_test",
            STAGE_LABELS["limited_core_grid_test"],
            limited_core,
            input_kind="market_sessions",
            detail="Deterministic shortlist slice selected before performance testing.",
        )
    )
    rows.append(
        _planned_window_row(
            "limited_monkey_test",
            STAGE_LABELS["limited_monkey_test"],
            limited_core,
            input_kind="market_sessions",
            inherited_from="limited_core_grid_test",
            detail="Uses the same shortlist market slice as limited core.",
        )
    )

    wfa_cfg = canonical.get("wfa") or {}
    wfa_subset = _stage_subset(
        canonical,
        campaign_tests.get("walk_forward_analysis") or {},
        "wfa",
    )
    wfa_detail = (
        f"Rolling {int(wfa_cfg.get('train_months', 48))}-month train / "
        f"{int(wfa_cfg.get('test_months', 12))}-month test / "
        f"{int(wfa_cfg.get('step_months', wfa_cfg.get('test_months', 12)))}-month step."
    )
    rows.append(
        _planned_window_row(
            "walk_forward_analysis",
            STAGE_LABELS["walk_forward_analysis"],
            wfa_subset,
            input_kind="rolling_market_windows",
            detail=wfa_detail,
        )
    )
    for stage_name in ("wfa_oos_monkey_test", "wfa_oos_monte_carlo"):
        rows.append(
            _planned_window_row(
                stage_name,
                STAGE_LABELS[stage_name],
                wfa_subset,
                input_kind="derived_trades",
                inherited_from="walk_forward_analysis",
                detail="Consumes only the stitched walk-forward out-of-sample trades.",
            )
        )

    incubation_cfg = campaign_tests.get("simulated_incubation_core") or {}
    incubation_base = _acceptance_base_subset(canonical, incubation_cfg)
    try:
        incubation_subset, incubation_window = _planned_acceptance_subset(
            incubation_base,
            int(incubation_cfg.get("train_months", 48)),
            int(incubation_cfg.get("test_months", 12)),
            stage_label="simulated_incubation_core",
            holdout_months=int(incubation_cfg.get("holdout_after_test_months", 0)),
        )
        rows.append(
            _planned_window_row(
                "simulated_incubation_core",
                STAGE_LABELS["simulated_incubation_core"],
                incubation_subset,
                input_kind="train_test_market_window",
                window=incubation_window,
                detail="Incubation OOS ends before the locked acceptance holdout begins.",
            )
        )
        rows.append(
            _planned_window_row(
                "simulated_incubation_monkey",
                STAGE_LABELS["simulated_incubation_monkey"],
                incubation_subset,
                input_kind="derived_trades",
                inherited_from="simulated_incubation_core",
                window=incubation_window,
                detail="Consumes only simulated-incubation OOS trades.",
            )
        )
    except ValueError as exc:
        rows.append(
            _unavailable_window_row(
                "simulated_incubation_core",
                STAGE_LABELS["simulated_incubation_core"],
                incubation_base,
                input_kind="train_test_market_window",
                detail=str(exc),
            )
        )
        rows.append(
            _unavailable_window_row(
                "simulated_incubation_monkey",
                STAGE_LABELS["simulated_incubation_monkey"],
                incubation_base,
                input_kind="derived_trades",
                inherited_from="simulated_incubation_core",
                detail=f"Inherited incubation window is unavailable: {exc}",
            )
        )

    acceptance_cfg = campaign_tests.get(ACCEPTANCE_STAGE) or {}
    acceptance_base = _acceptance_base_subset(canonical, acceptance_cfg)
    try:
        acceptance_subset, acceptance_window = _planned_acceptance_subset(
            acceptance_base,
            int(acceptance_cfg.get("train_months", 24)),
            int(acceptance_cfg.get("test_months", 6)),
            stage_label=ACCEPTANCE_STAGE,
        )
        rows.append(
            _planned_window_row(
                ACCEPTANCE_STAGE,
                STAGE_LABELS[ACCEPTANCE_STAGE],
                acceptance_subset,
                input_kind="train_test_market_window",
                window=acceptance_window,
                detail="Final locked holdout; excluded from WFA and incubation OOS.",
            )
        )
    except ValueError as exc:
        rows.append(
            _unavailable_window_row(
                ACCEPTANCE_STAGE,
                STAGE_LABELS[ACCEPTANCE_STAGE],
                acceptance_base,
                input_kind="train_test_market_window",
                detail=str(exc),
            )
        )
    return rows


def _planned_window_row(
    stage: str,
    label: str,
    subset: dict | None,
    *,
    input_kind: str,
    detail: str,
    inherited_from: str | None = None,
    window: dict | None = None,
) -> dict[str, Any]:
    subset = dict(subset or {})
    window = window or {}
    row = {
        "stage": stage,
        "label": label,
        "input_kind": input_kind,
        "inherited_from": inherited_from,
        "planned_start": subset.get("start_date") or subset.get("start_timestamp"),
        "planned_end": subset.get("end_date") or subset.get("end_timestamp"),
        "train_start": _planned_timestamp_date(window.get("train_start")),
        "train_end": _planned_timestamp_date(window.get("train_end")),
        "test_start": _planned_timestamp_date(window.get("test_start")),
        "test_end": _planned_timestamp_date(window.get("test_end")),
        "detail": detail,
        "status": "planned",
    }
    start = _subset_start_date(subset)
    end = _subset_end_date(subset)
    if start is not None and end is not None and start > end:
        row["status"] = "unavailable"
        row["detail"] = (
            f"{detail} The planned end {end.date().isoformat()} precedes the "
            f"available start {start.date().isoformat()}."
        )
    return row


def _unavailable_window_row(
    stage: str,
    label: str,
    subset: dict | None,
    *,
    input_kind: str,
    detail: str,
    inherited_from: str | None = None,
) -> dict[str, Any]:
    row = _planned_window_row(
        stage,
        label,
        subset,
        input_kind=input_kind,
        inherited_from=inherited_from,
        detail=detail,
    )
    row["status"] = "unavailable"
    return row


def _planned_timestamp_date(value: Any) -> str | None:
    if value is None:
        return None
    return pd.Timestamp(value).date().isoformat()


def apply_fast_runtime_defaults(cfg: dict, workers: int | None = None) -> dict:
    out = copy.deepcopy(cfg)
    # WFA workers keep sliced market/detail frames cached across windows. A lower
    # default avoids memory-heavy process-pool stalls while preserving mechanics.
    worker_count = max(1, int(workers or min(3, os.cpu_count() or 1)))
    _enable_parallel(out, "core_grid", "grid", worker_count)
    _enable_parallel(out, "monkey", "runs", worker_count)
    _enable_parallel(out, "wfa", "window_grid", worker_count)
    _enable_parallel(out, "monte_carlo", "runs", worker_count)

    campaign_tests = out.get("campaign_tests") or {}
    for stage_name, scope in [
        ("limited_core_grid_test", "grid"),
        ("limited_monkey_test", "runs"),
        ("walk_forward_analysis", "window_grid"),
        ("wfa_oos_monkey_test", "runs"),
        ("wfa_oos_monte_carlo", "runs"),
        ("simulated_incubation_monkey", "runs"),
        (ACCEPTANCE_STAGE, "grid"),
    ]:
        stage_cfg = campaign_tests.get(stage_name)
        if isinstance(stage_cfg, dict):
            _enable_parallel(stage_cfg, None, scope, worker_count)
    incubation = campaign_tests.get("simulated_incubation_core") or {}
    train_selection = incubation.get("train_selection")
    if isinstance(train_selection, dict):
        _enable_parallel(train_selection, None, "grid", worker_count)
    return out


def _require_attempt_contract(
    cfg: dict[str, Any],
    config_path: Path,
    *,
    out_dir: str | Path | None,
) -> dict[str, Any]:
    """Enforce one immutable staged run for each governance-v2 authored attempt."""

    version = _campaign_governance_version(cfg, config_path)
    attempt = {
        "attempt_id": cfg.get("attempt_id"),
        "attempt_kind": cfg.get("attempt_kind"),
        "attempt_provenance": cfg.get("attempt_provenance"),
        "parent_attempt_id": cfg.get("parent_attempt_id"),
    }
    if version < 2:
        return attempt

    attempt_id = str(attempt.get("attempt_id") or "")
    if re.fullmatch(r"[a-z0-9][a-z0-9_]*", attempt_id) is None:
        raise ValueError("governance-v2 staged runs require a lowercase authored attempt_id")
    if attempt.get("attempt_provenance") != "authored":
        raise ValueError("governance-v2 staged runs require attempt_provenance=authored")
    attempt_kind = str(attempt.get("attempt_kind") or "")
    if not attempt_kind:
        raise ValueError("governance-v2 staged runs require attempt_kind")
    if attempt_kind != "original" and not attempt.get("parent_attempt_id"):
        raise ValueError("non-original governance-v2 attempts require parent_attempt_id")

    campaign_id = str(cfg.get("campaign_id") or "")
    variant_id = str(cfg.get("variant_id") or "")
    proposed_root = Path(out_dir) if out_dir else variant_root(cfg, config_path=config_path)
    existing_at_root = _existing_run_summary(proposed_root)
    if existing_at_root is not None:
        raise ValueError(
            "immutable run directory already contains evidence; create a new attempt_id and test_run_id: "
            f"{proposed_root}"
        )

    variant_evidence_root = CAMPAIGN_REPORT_ROOT / campaign_id / variant_id
    summary_paths = {
        *variant_evidence_root.glob("*/*/campaign_test_summary.json"),
        *variant_evidence_root.glob("*/*/variant_test_summary.json"),
    }
    for summary_path in sorted(summary_paths):
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(summary.get("attempt_id") or "") == attempt_id:
            raise ValueError(
                "one-run-per-attempt violation; this governance-v2 attempt already has immutable evidence: "
                f"{summary_path.parent}"
            )
    return attempt


def _campaign_governance_version(cfg: dict[str, Any], config_path: Path) -> int:
    campaign_id = str(cfg.get("campaign_id") or "")
    campaign_root = _source_campaign_root(config_path)
    if campaign_root is not None:
        campaign_path = campaign_root / "campaign.yaml"
        if campaign_path.is_file():
            campaign = load_yaml(campaign_path)
            if str(campaign.get("campaign_id") or campaign_root.name) == campaign_id:
                return int(campaign.get("governance_contract_version") or 0)
    return 0


def _existing_run_summary(root: Path) -> Path | None:
    for filename in ("campaign_test_summary.json", VARIANT_TEST_SUMMARY_FILENAME):
        path = root / filename
        if path.is_file():
            return path
    return None


def _enable_parallel(container: dict, section: str | None, scope: str, workers: int) -> None:
    target = container.setdefault(section, {}) if section else container
    if not isinstance(target, dict):
        return
    parallel = copy.deepcopy(target.get("parallel") or {})
    parallel["enabled"] = True
    parallel["scope"] = scope
    parallel["workers"] = max(int(parallel.get("workers") or 1), workers)
    target["parallel"] = parallel


def _write_config_snapshot(path: Path, cfg: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(cfg, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def run_campaign_stage_tests(
    config_path: str | Path,
    *,
    skip_validation: bool = True,
    continue_on_failure: bool = False,
    out_dir: str | Path | None = None,
    include_acceptance: bool = True,
    fast_runtime_defaults: bool = False,
) -> dict:
    config_path = Path(config_path)
    source_config_text = config_path.read_text(encoding="utf-8")
    source_config_hash = hashlib.sha256(source_config_text.encode("utf-8")).hexdigest()
    diagnostic_reasons = _diagnostic_reasons(
        skip_validation=skip_validation,
        include_acceptance=include_acceptance,
        fast_runtime_defaults=fast_runtime_defaults,
    )
    submission_preflight = run_preflight(
        config_paths=[config_path],
        # The staged submission invokes the complete campaign/config/data
        # checks. Repository tests remain an installation/CI gate; running
        # pytest from here would recursively execute staged-run tests.
        run_tests=False,
        project_root=_storage_project_root(config_path),
    )
    if not submission_preflight["passed"] and not diagnostic_reasons:
        raise ValueError(
            "Staged submission preflight failed before attempt reservation:\n- "
            + "\n- ".join(submission_preflight["failures"])
        )
    cfg = canonicalize_campaign_config(load_yaml(config_path), include_acceptance=include_acceptance)
    _validate_pre_test_mechanics_review(cfg, config_path)
    validation_gate = require_validation_approval(cfg, config_path)
    require_prior_variant_approvals(cfg, config_path)
    attempt = _require_attempt_contract(cfg, config_path, out_dir=out_dir)
    if fast_runtime_defaults:
        cfg = apply_fast_runtime_defaults(cfg)
    root = Path(out_dir) if out_dir else variant_root(cfg, config_path=config_path)
    root = validate_campaign_run_root(root, cfg, config_path=config_path if out_dir is None else None)
    validate_campaign_config_contract(cfg, context=str(config_path))
    root.mkdir(parents=True, exist_ok=True)
    variant_metadata = ensure_variant_metadata(cfg, root_path=root)
    config_snapshot_path = root / CAMPAIGN_CONFIG_FILENAME
    source_config_snapshot_path = root / SOURCE_CONFIG_SNAPSHOT_FILENAME
    _write_config_snapshot(config_snapshot_path, cfg)
    if config_path.resolve() != source_config_snapshot_path.resolve():
        source_config_snapshot_path.write_text(source_config_text, encoding="utf-8")

    campaign_tests = cfg.get("campaign_tests") or {}
    stage_order = _stage_order(campaign_tests)
    context: dict[str, Any] = {"_prepared_data_cache": {}}
    results = []
    halted = False

    for stage_name in stage_order:
        if halted:
            results.append(_skipped_stage(stage_name, "prior stage failed"))
            continue
        stage_cfg = _stage_config(campaign_tests, stage_name)
        if stage_cfg.get("enabled", True) is False:
            results.append(_skipped_stage(stage_name, "disabled"))
            continue

        stage_dir = root / stage_name
        stage_dir.mkdir(parents=True, exist_ok=True)
        try:
            result = _run_stage(
                stage_name,
                cfg,
                config_path,
                stage_cfg,
                stage_dir,
                skip_validation,
                context,
            )
        except Exception as exc:
            result = _error_stage(stage_name, exc)
        results.append(result)
        validate_stage_result_contract(result, context=f"{stage_name}/stage_result.json")
        write_json(stage_dir / "stage_result.json", result)
        if not result["passed"] and not continue_on_failure:
            halted = True

    created_at = datetime.now().isoformat(timespec="seconds")
    run_uid = ensure_run_uid(root)
    data_cfg = cfg.get("data") or {}
    research_verdict = _research_verdict(results, diagnostic_reasons)
    summary = {
        "run_uid": run_uid,
        "campaign_id": cfg.get("campaign_id"),
        "variant_id": cfg.get("variant_id"),
        "test_run_id": campaign_test_run_id(cfg, config_path=config_path, root_path=root),
        "attempt_id": attempt.get("attempt_id"),
        "attempt_kind": attempt.get("attempt_kind"),
        "attempt_provenance": attempt.get("attempt_provenance"),
        "parent_attempt_id": attempt.get("parent_attempt_id"),
        "symbol": cfg.get("symbol") or (cfg.get("data") or {}).get("symbol"),
        "dataset_id": cfg.get("dataset_id") or (cfg.get("data") or {}).get("dataset_id"),
        "timeframe": config_timeframe(cfg),
        "data_source": _data_source_name(data_cfg),
        "raw_csv": str(data_cfg.get("raw_csv")) if data_cfg.get("raw_csv") else None,
        "raw_parquet": str(data_cfg.get("raw_parquet")) if data_cfg.get("raw_parquet") else None,
        "raw_dir": str(data_cfg.get("raw_dir")) if data_cfg.get("raw_dir") else None,
        "campaign_metadata": campaign_metadata_info(cfg, root_path=root),
        "variant_metadata": variant_metadata,
        "research_policy": cfg.get("research_policy") or active_research_policy_metadata(),
        "engine_contract_version": ENGINE_CONTRACT_VERSION,
        "config_path": str(config_snapshot_path),
        "effective_config_path": str(config_snapshot_path),
        "source_config_path": str(config_path),
        "source_config_snapshot_path": str(source_config_snapshot_path),
        "config_hash": file_sha256(config_snapshot_path),
        "source_config_hash": source_config_hash,
        "output_dir": str(root),
        "created_at": created_at,
        "updated_at": created_at,
        "skip_validation": skip_validation,
        "mechanics_validation_gate": validation_gate,
        "fast_runtime_defaults": fast_runtime_defaults,
        "submission_preflight": submission_preflight,
        "diagnostic_only": bool(diagnostic_reasons),
        "diagnostic_reasons": diagnostic_reasons,
        "research_verdict": research_verdict,
        "passed": research_verdict == "PASS",
        "halted": halted,
        "stages": results,
    }
    validate_run_summary_contract(summary)
    source_results_index_path = _update_source_results_index(config_path, cfg, summary)
    summary["source_results_index_path"] = (
        str(source_results_index_path) if source_results_index_path is not None else None
    )
    write_json(
        root / "run_manifest.json",
        {
            "run_uid": run_uid,
            "campaign_id": summary["campaign_id"],
            "variant_id": summary["variant_id"],
            "test_run_id": summary["test_run_id"],
            "attempt_id": summary["attempt_id"],
            "attempt_kind": summary["attempt_kind"],
            "attempt_provenance": summary["attempt_provenance"],
            "parent_attempt_id": summary["parent_attempt_id"],
            "symbol": summary["symbol"],
            "dataset_id": summary["dataset_id"],
            "timeframe": summary["timeframe"],
            "data_source": summary["data_source"],
            "raw_csv": summary["raw_csv"],
            "raw_parquet": summary["raw_parquet"],
            "raw_dir": summary["raw_dir"],
            "campaign_metadata": summary["campaign_metadata"],
            "variant_metadata": summary["variant_metadata"],
            "research_policy": summary["research_policy"],
            "engine_contract_version": summary["engine_contract_version"],
            "config_source": str(config_path),
            "effective_config": str(config_snapshot_path),
            "source_config_snapshot": str(source_config_snapshot_path),
            "config_hash": summary["config_hash"],
            "source_config_hash": source_config_hash,
            "source_results_index": summary["source_results_index_path"],
            "created_at": created_at,
            "updated_at": created_at,
            "stage_order": stage_order,
            "mechanics_validation_gate": validation_gate,
            "submission_preflight": submission_preflight,
            "diagnostic_only": summary["diagnostic_only"],
            "diagnostic_reasons": diagnostic_reasons,
            "research_verdict": research_verdict,
            "layout": "campaign_variant_symbol_run",
        },
    )
    write_json(root / "campaign_test_summary.json", summary)
    write_json(root / VARIANT_TEST_SUMMARY_FILENAME, summary)
    (root / "campaign_test_summary.md").write_text(_markdown_summary(summary), encoding="utf-8")
    if research_verdict == "PASS":
        _write_candidate_due_diligence_package(root, cfg, summary, config_snapshot_path)
    update_runs_index(root)
    return summary


def _update_source_results_index(config_path: Path, cfg: dict, summary: dict) -> Path | None:
    """Write a lightweight source-tree pointer to generated evidence.

    The generated evidence stays under backtest-campaigns. This index only gives
    source configs a stable navigation hook to the run folder that tested them.
    """

    context = resolve_campaign_context(config_path, project_root=_storage_project_root(config_path))
    if context is None or context.campaign_id != str(cfg.get("campaign_id")):
        return None
    index_path = context.results_index
    existing = load_yaml(index_path) if index_path.is_file() else {}
    entries = existing.get("runs") if isinstance(existing.get("runs"), list) else []
    run_dir = Path(str(summary["output_dir"]))
    entry = {
        "campaign_id": summary.get("campaign_id"),
        "variant_id": summary.get("variant_id"),
        "symbol": summary.get("symbol"),
        "test_run_id": summary.get("test_run_id"),
        "attempt_id": summary.get("attempt_id"),
        "attempt_kind": summary.get("attempt_kind"),
        "attempt_provenance": summary.get("attempt_provenance"),
        "parent_attempt_id": summary.get("parent_attempt_id"),
        "source_config_path": str(config_path),
        "source_config_snapshot_path": summary.get("source_config_snapshot_path"),
        "source_config_hash": summary.get("source_config_hash"),
        "effective_config_path": summary.get("effective_config_path"),
        "effective_config_hash": summary.get("config_hash"),
        "run_dir": str(run_dir),
        "campaign_test_summary": str(run_dir / "campaign_test_summary.json"),
        "variant_test_summary": str(run_dir / VARIANT_TEST_SUMMARY_FILENAME),
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
    key_fields = ("source_config_path", "symbol", "test_run_id")
    entries = [
        item
        for item in entries
        if not all(str(item.get(field)) == str(entry.get(field)) for field in key_fields)
    ]
    entries.append(entry)
    entries.sort(
        key=lambda item: (
            str(item.get("variant_id") or ""),
            str(item.get("symbol") or ""),
            str(item.get("test_run_id") or ""),
            str(item.get("source_config_path") or ""),
        )
    )
    payload = {
        "campaign_id": cfg.get("campaign_id"),
        "generated_by": "alphaquest.run_campaign_stages",
        "description": "Navigation pointers from authored source configs to generated backtest evidence.",
        "runs": entries,
    }
    index_path.write_text(yaml.safe_dump(payload, sort_keys=False, default_flow_style=False), encoding="utf-8")
    return index_path


def update_source_results_index(config_path: Path, cfg: dict, summary: dict) -> Path | None:
    """Publish a source-tree run pointer from a non-staged campaign runner."""

    return _update_source_results_index(config_path, cfg, summary)


def _source_campaign_root(config_path: Path) -> Path | None:
    context = resolve_campaign_context(config_path, project_root=_storage_project_root(config_path))
    return context.campaign_root if context is not None else None


def _storage_project_root(config_path: Path) -> Path:
    resolved = config_path.resolve()
    for parent in resolved.parents:
        if (parent / "config" / "storage_layout.yaml").is_file():
            return parent
    return Path.cwd()


def _diagnostic_reasons(
    *,
    skip_validation: bool,
    include_acceptance: bool,
    fast_runtime_defaults: bool,
) -> list[str]:
    reasons: list[str] = []
    if skip_validation:
        reasons.append("staged data validation artifacts were skipped")
    if not include_acceptance:
        reasons.append(f"mandatory {ACCEPTANCE_STAGE} was omitted")
    if fast_runtime_defaults:
        reasons.append("fast runtime defaults were applied")
    return reasons


def _research_verdict(results: list[dict], diagnostic_reasons: list[str]) -> str:
    if diagnostic_reasons:
        return "NEEDS MANUAL REVIEW"
    statuses = [str(result.get("status") or "") for result in results]
    stage_names = [str(result.get("stage") or "") for result in results]
    if stage_names == DEFAULT_STAGE_ORDER and statuses == ["passed"] * len(DEFAULT_STAGE_ORDER):
        return "PASS"
    if any(status == "failed" for status in statuses):
        return "FAIL"
    return "NEEDS MANUAL REVIEW"


def _first_failed_stage(stages: list[dict]) -> str | None:
    for stage in stages:
        if stage.get("status") == "failed" or stage.get("passed") is False:
            return str(stage.get("stage") or "")
    return None


def _validate_pre_test_mechanics_review(cfg: dict, config_path: Path) -> None:
    """Require the pre-result mechanics rationale before any staged test starts."""

    failures: list[str] = []
    prefix = str(config_path)
    research = cfg.get("research_metadata")
    if not isinstance(research, dict):
        failures.append(f"{prefix}: research_metadata must include a pre-test mechanics review.")
    else:
        if not bool(research.get("mechanics_review_required") or research.get("mechanics_review_version")):
            failures.append(
                f"{prefix}: research_metadata.mechanics_review_required must be true before staged testing."
            )
        review = research.get("mechanics_review")
        if not isinstance(review, dict):
            failures.append(f"{prefix}: research_metadata.mechanics_review must be configured before staged testing.")
        else:
            for field in REQUIRED_MECHANICS_REVIEW_FIELDS:
                value = review.get(field)
                if not isinstance(value, str) or len(value.strip()) < MECHANICS_REVIEW_MIN_CHARS:
                    failures.append(
                        f"{prefix}: research_metadata.mechanics_review.{field} must be a detailed pre-test rationale."
                    )
            decision = str(review.get("pre_test_decision", "")).strip().lower()
            if decision != "approve_for_testing":
                failures.append(
                    f"{prefix}: research_metadata.mechanics_review.pre_test_decision must be approve_for_testing."
                )

    if failures:
        raise ValueError("Pre-test mechanics review failed:\n- " + "\n- ".join(failures))


def _write_candidate_due_diligence_package(
    root: Path,
    cfg: dict,
    summary: dict,
    config_snapshot_path: Path,
) -> None:
    """Write the promotion package only after the top-level staged summary passes."""

    shutil.copy2(config_snapshot_path, root / "final_config.yaml")
    _copy_if_exists(root / ACCEPTANCE_STAGE / "trade_log.csv", root / "final_trade_log.csv")
    _copy_if_exists(root / ACCEPTANCE_STAGE / "trade_log.csv", root / "validation_trade_log.csv")
    _copy_if_exists(root / ACCEPTANCE_STAGE / "equity_curve.csv", root / "final_equity_curve.csv")
    _copy_if_exists(root / "walk_forward_analysis" / "wfa_oos_trade_log.csv", root / "WFA_trade_log.csv")
    _copy_if_exists(root / "wfa_oos_monte_carlo" / "wfa_oos_monte_carlo_summary.json", root / "MonteCarlo_summary.json")
    (root / "candidate_strategy_report.md").write_text(
        _candidate_strategy_report(cfg, summary),
        encoding="utf-8",
    )
    (root / "manual_due_diligence_checklist.md").write_text(
        _manual_due_diligence_checklist(root, cfg, summary),
        encoding="utf-8",
    )


def _copy_if_exists(source: Path, destination: Path) -> None:
    if source.is_file():
        shutil.copy2(source, destination)


def _candidate_strategy_report(cfg: dict, summary: dict) -> str:
    strategy = cfg.get("strategy") or {}
    entry = strategy.get("entry") or {}
    sl = strategy.get("sl") or {}
    tp = strategy.get("tp") or {}
    research = cfg.get("research_metadata") or {}
    lines = [
        "# Candidate Strategy Report",
        "",
        "Final decision: PASS - candidate for manual due diligence",
        "",
        "## Strategy Summary",
        "",
        f"- Campaign: `{cfg.get('campaign_id')}`",
        f"- Variant: `{cfg.get('variant_id')}`",
        f"- Instrument: `{summary.get('symbol')}`",
        f"- Dataset: `{summary.get('dataset_id')}`",
        f"- Timeframe: `{summary.get('timeframe')}`",
        f"- Edge hypothesis: {research.get('edge_thesis', 'See campaign metadata.')}",
        f"- Research basis: {research.get('academic_source', 'See campaign metadata.')}",
        f"- Entry module: `{entry.get('module')}` with params `{entry.get('params', {})}`",
        f"- Stop module: `{sl.get('module')}` with params `{sl.get('params', {})}`",
        f"- Target module: `{tp.get('module')}` with params `{tp.get('params', {})}`",
        f"- Forced flatten: `{strategy.get('flatten_time')}`",
        "",
        "## Evidence Summary",
        "",
    ]
    for stage in summary.get("stages", []):
        lines.append(
            f"- {stage.get('stage')}: {stage.get('status')} "
            f"({stage.get('duration_seconds', 0):.1f}s)"
        )
    lines.extend(
        [
            "",
            "## Tradeability Assessment",
            "",
            "- This is a candidate strategy, not a live-trading approval.",
            "- Manual chart review and paper/live incubation are still required before trading.",
            "- Review forced-flatten timing, stop/target ordering, and worst drawdown trades before any deployment.",
            "",
            "## Final Decision",
            "",
            "PASS - candidate for manual due diligence",
            "",
        ]
    )
    return "\n".join(lines)


def _manual_due_diligence_checklist(root: Path, cfg: dict, summary: dict) -> str:
    trade_log = root / "final_trade_log.csv"
    sections = _due_diligence_trade_sections(trade_log)
    lines = [
        "# Manual Due Diligence Checklist",
        "",
        f"Campaign: `{cfg.get('campaign_id')}`",
        f"Variant: `{cfg.get('variant_id')}`",
        f"Evidence: `{root / 'campaign_test_summary.json'}`",
        "",
        "Use these rows for manual chart review before paper/live incubation.",
        "",
    ]
    for title, rows in sections.items():
        lines.extend([f"## {title}", ""])
        if not rows:
            lines.extend(["- No trades available in this category.", ""])
            continue
        for row in rows:
            lines.append(
                "- "
                f"timestamp={row.get('entry_timestamp', '')}; "
                f"direction={row.get('direction', '')}; "
                f"entry={row.get('entry_price', '')}; "
                f"exit={row.get('exit_price', '')}; "
                f"exit_reason={row.get('exit_reason', '')}; "
                f"net_pnl={row.get('net_pnl', '')}; "
                "chart_review_notes="
            )
        lines.append("")
    lines.append("Final decision: PASS - candidate for manual due diligence")
    lines.append("")
    return "\n".join(lines)


def _due_diligence_trade_sections(trade_log: Path) -> dict[str, list[dict]]:
    if not trade_log.is_file():
        return {
            "20 Random Trades": [],
            "10 Biggest Winners": [],
            "10 Biggest Losers": [],
            "10 Forced-Flatten / Late Exits": [],
            "Worst Drawdown Sample": [],
        }
    trades = pd.read_csv(trade_log)
    if trades.empty:
        return {
            "20 Random Trades": [],
            "10 Biggest Winners": [],
            "10 Biggest Losers": [],
            "10 Forced-Flatten / Late Exits": [],
            "Worst Drawdown Sample": [],
        }
    if "net_pnl" in trades.columns:
        trades["net_pnl"] = pd.to_numeric(trades["net_pnl"], errors="coerce")
    random_rows = trades.sample(min(20, len(trades)), random_state=7).to_dict("records")
    winners = trades.sort_values("net_pnl", ascending=False).head(10).to_dict("records") if "net_pnl" in trades else []
    losers = trades.sort_values("net_pnl", ascending=True).head(10).to_dict("records") if "net_pnl" in trades else []
    late_mask = pd.Series(False, index=trades.index)
    for column in ["was_forced_flatten", "exit_reason"]:
        if column in trades.columns:
            late_mask = late_mask | trades[column].astype(str).str.contains("flatten|eod", case=False, na=False)
    late = trades[late_mask].tail(10).to_dict("records")
    drawdown = _worst_drawdown_rows(trades).to_dict("records") if "net_pnl" in trades else []
    return {
        "20 Random Trades": random_rows,
        "10 Biggest Winners": winners,
        "10 Biggest Losers": losers,
        "10 Forced-Flatten / Late Exits": late,
        "Worst Drawdown Sample": drawdown,
    }


def _worst_drawdown_rows(trades: pd.DataFrame) -> pd.DataFrame:
    ordered = _trade_order_for_due_diligence(trades)
    equity = ordered["net_pnl"].fillna(0.0).cumsum()
    peaks = equity.cummax()
    drawdown = peaks - equity
    if drawdown.empty:
        return ordered.head(0)
    trough_idx = int(drawdown.idxmax())
    peak_value = peaks.loc[trough_idx]
    prior = equity.loc[:trough_idx]
    peak_matches = prior[prior == peak_value]
    start_idx = int(peak_matches.index[-1]) if not peak_matches.empty else max(0, trough_idx - 20)
    return ordered.loc[start_idx:trough_idx].tail(30)


def _trade_order_for_due_diligence(trades: pd.DataFrame) -> pd.DataFrame:
    if "exit_timestamp" not in trades.columns:
        return trades.reset_index(drop=True)
    out = trades.copy()
    out["_exit_order"] = pd.to_datetime(out["exit_timestamp"], errors="coerce", utc=True)
    return out.sort_values("_exit_order", kind="mergesort").drop(columns=["_exit_order"]).reset_index(drop=True)


def _run_stage(
    stage_name: str,
    cfg: dict,
    config_path: Path,
    stage_cfg: dict,
    stage_dir: Path,
    skip_validation: bool,
    context: dict,
) -> dict:
    started = datetime.now()
    if stage_name == "limited_core_grid_test":
        payload = _run_limited_core_grid(cfg, stage_cfg, stage_dir, skip_validation, context)
        context["limited_core_grid_results"] = payload.get("core_grid_results")
        context["limited_core_grid_parameters"] = payload.get("core_grid_parameters") or {}
    elif stage_name == "limited_monkey_test":
        payload = _run_limited_monkey(cfg, stage_cfg, stage_dir, skip_validation, context)
    elif stage_name == "walk_forward_analysis":
        payload = _run_wfa_stage(cfg, stage_cfg, stage_dir, skip_validation, context)
        context["wfa_trades"] = payload.get("trades")
        context["wfa_market"] = payload.get("market")
        context["wfa_detail"] = payload.get("detail")
        context["incubation_params"] = payload.get("incubation_selected_params", {})
    elif stage_name == "wfa_oos_monkey_test":
        payload = _run_wfa_oos_monkey(cfg, stage_cfg, stage_dir, context)
    elif stage_name == "wfa_oos_monte_carlo":
        payload = _run_wfa_oos_monte_carlo(cfg, stage_cfg, stage_dir, context)
    elif stage_name == "simulated_incubation_core":
        payload = _run_incubation_core(cfg, stage_cfg, stage_dir, skip_validation, context)
        context["incubation_trades"] = payload.get("trades")
        context["incubation_market"] = payload.get("market")
        context["incubation_detail"] = payload.get("detail")
        context["incubation_config"] = payload.get("test_config")
    elif stage_name == "simulated_incubation_monkey":
        payload = _run_incubation_monkey(cfg, stage_cfg, stage_dir, context)
    elif stage_name == ACCEPTANCE_STAGE:
        payload = _run_acceptance_oos(cfg, stage_cfg, stage_dir, skip_validation, context)
    else:
        raise ValueError(f"Unsupported campaign test stage: {stage_name}")

    criteria = _criteria_for_stage(stage_name, stage_cfg)
    criteria_results = evaluate_criteria(payload, criteria)
    passed = all(item["passed"] for item in criteria_results)
    completed = datetime.now()
    public_payload = {
        k: v
        for k, v in payload.items()
        if k not in {"trades", "market", "detail", "core_grid_results", "test_config"}
    }
    return {
        "stage": stage_name,
        "label": STAGE_LABELS.get(stage_name, stage_name),
        "status": "passed" if passed else "failed",
        "passed": passed,
        "started_at": started.isoformat(timespec="seconds"),
        "completed_at": completed.isoformat(timespec="seconds"),
        "duration_seconds": (completed - started).total_seconds(),
        "criteria": criteria_results,
        **public_payload,
    }


def _run_limited_core_grid(
    cfg: dict,
    stage_cfg: dict,
    stage_dir: Path,
    skip_validation: bool,
    context: dict,
) -> dict:
    grid_cfg = _merged_section(cfg, "core_grid", stage_cfg)
    subset = _stage_subset(cfg, stage_cfg, "core_grid")
    benchmarks, benchmark_adjustments = _limited_core_grid_benchmarks(cfg, subset)
    market, detail, quality, input_hash = _prepare_stage_data_cached(
        cfg,
        subset,
        stage_dir,
        skip_validation,
        data_cache=context.get("_prepared_data_cache"),
    )
    fixed_config_core = _write_fixed_config_core_artifacts(cfg, market, detail, stage_dir, subset, quality)
    report_dir = stage_dir if grid_cfg.get("retain_iteration_reports", True) else None
    results, summary = run_core_grid(
        market,
        cfg,
        grid_cfg,
        benchmarks,
        report_dir=report_dir,
        detail_data=detail,
    )
    summary["benchmark_thresholds"] = benchmarks
    summary["benchmark_threshold_adjustments"] = benchmark_adjustments
    summary["fixed_config_core"] = fixed_config_core
    _annotate_stage_data_period(summary, subset, quality)
    report_timezone = market_timezone(cfg)
    write_report_csv(results, stage_dir / "core_grid_results.csv", report_timezone, index=False)
    write_json(stage_dir / "core_grid_summary.json", summary)
    artifacts = _stage_artifacts(stage_dir)
    return {
        "summary": summary,
        "data_quality": quality,
        "input_hash": input_hash,
        "artifacts": artifacts,
        "market": market,
        "detail": detail,
        "core_grid_results": results,
        "core_grid_parameters": grid_cfg.get("parameters", {}),
    }


def _write_fixed_config_core_artifacts(
    cfg: dict,
    market: pd.DataFrame,
    detail: pd.DataFrame | None,
    stage_dir: Path,
    resolved_subset: dict | None,
    quality: dict,
) -> dict:
    """Write a YAML-fixed strategy run for chart/mechanics cross-checking.

    This run deliberately uses the parameters already present under
    strategy.entry/sl/tp in the effective config. It does not use grid-selected,
    monkey-selected, WFA-selected, or rescue-derived parameters.
    """

    result = run_research_backtest(cfg, market, detail_data=detail, bar_engine_cls=BacktestEngine)
    trades = result.get("trades", pd.DataFrame())
    daily = result.get("daily", pd.DataFrame())
    report_timezone = market_timezone(cfg)
    trade_log_path = stage_dir / "fixed_config_core_trade_log.csv"
    daily_path = stage_dir / "fixed_config_core_daily_results.csv"
    write_report_csv(trades, trade_log_path, report_timezone, index=False)
    write_report_csv(daily, daily_path, report_timezone, index=False)
    initial_balance = float((cfg.get("core") or {}).get("initial_balance", 0.0))
    equity_summary = write_equity_report(
        trades,
        stage_dir,
        initial_balance=initial_balance,
        timezone=report_timezone,
        title=f"{cfg.get('campaign_id')} / {cfg.get('variant_id')} fixed-config core equity curve",
        csv_name="fixed_config_core_equity_curve.csv",
        html_name="fixed_config_core_equity_curve.html",
        write_html=_retain_artifact(cfg, "equity_html"),
    )
    summary = {
        "purpose": "fixed_config_mechanics_cross_check",
        "parameter_source": "strategy section in effective config",
        "uses_grid_selected_params": False,
        "trade_log_csv": str(trade_log_path),
        "daily_results_csv": str(daily_path),
        "metrics": copy.deepcopy(result.get("metrics", {})),
        "diagnostics": copy.deepcopy(result.get("diagnostics", {})),
        "strategy": copy.deepcopy(cfg.get("strategy", {})),
        "core": copy.deepcopy(cfg.get("core", {})),
        **equity_summary,
    }
    _annotate_stage_data_period(summary, resolved_subset, quality)
    write_json(stage_dir / "fixed_config_core_metrics.json", summary)
    return summary


def _limited_core_grid_benchmarks(cfg: dict, resolved_subset: dict | None) -> tuple[dict, dict]:
    base = copy.deepcopy(cfg.get("benchmarks") or {})
    out = {key: copy.deepcopy(base[key]) for key in LIMITED_CORE_GRID_BENCHMARK_KEYS if key in base}
    adjustments: dict[str, Any] = {"mode": "limited_core_grid_screen"}
    stage_years = _subset_span_years(resolved_subset)
    full_subset = (cfg.get("core") or {}).get("data_subset") or (cfg.get("data") or {}).get("data_subset") or {}
    full_years = _subset_span_years(full_subset)
    adjustments["stage_years"] = stage_years
    adjustments["configured_full_years"] = full_years

    min_count_candidates = []
    min_trades_per_year = _positive_float(base.get("min_trades_per_year"))
    if min_trades_per_year is not None and stage_years is not None:
        min_count_candidates.append(math.ceil(min_trades_per_year * stage_years))

    for key in ("min_trade_count", "preferred_min_total_trades"):
        value = _positive_float(base.get(key))
        if value is None:
            continue
        adjusted = value
        if stage_years is not None and full_years is not None and 0 < stage_years < full_years:
            adjusted = value * stage_years / full_years
        adjusted_count = max(1, int(math.ceil(adjusted)))
        if key in out:
            out[key] = adjusted_count
        min_count_candidates.append(adjusted_count)
        adjustments[key] = {
            "original": value,
            "adjusted": adjusted_count,
        }

    if min_count_candidates:
        out["preferred_min_total_trades"] = max(int(value) for value in min_count_candidates)
        adjustments["effective_preferred_min_total_trades"] = out["preferred_min_total_trades"]

    adjustments["included_thresholds"] = sorted(out)
    adjustments["excluded_full_stage_thresholds"] = sorted(
        key for key in base if key not in out and key != "min_trades_per_year"
    )
    return out, adjustments


def _positive_float(value) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric) or numeric <= 0:
        return None
    return numeric


def _subset_span_years(subset: dict | None) -> float | None:
    if not subset:
        return None
    start = _subset_start_date(subset)
    end = _subset_end_date(subset)
    if start is None or end is None:
        return None
    days = max((end - start).days + 1, 1)
    return float(days / 365.25)


def _annotate_stage_data_period(summary: dict, resolved_subset: dict | None, quality: dict) -> None:
    configured_subset = copy.deepcopy(summary.get("data_subset") or {})
    actual_period = {
        "first_timestamp": quality.get("first_timestamp"),
        "last_timestamp": quality.get("last_timestamp"),
        "rows": quality.get("rows"),
        "strategy_rows": quality.get("strategy_rows"),
        "timeframe": quality.get("timeframe"),
        "source_timeframe": quality.get("source_timeframe"),
    }
    summary["configured_data_subset"] = configured_subset
    summary["resolved_data_subset"] = copy.deepcopy(resolved_subset or {})
    summary["data_subset"] = copy.deepcopy(resolved_subset or {})
    summary["actual_data_period"] = actual_period


def _skipped_trade_path_stress() -> tuple[pd.DataFrame, dict]:
    return (
        pd.DataFrame(columns=["run_id", "skipped", "skip_reason"]),
        {
            "enabled": False,
            "skipped": True,
            "skip_reason": TRADE_PATH_STRESS_SKIP_REASON,
        },
    )


def _run_limited_monkey(
    cfg: dict,
    stage_cfg: dict,
    stage_dir: Path,
    skip_validation: bool,
    context: dict,
) -> dict:
    monkey_cfg = _merged_section(cfg, "monkey", stage_cfg)
    subset = _stage_subset(cfg, stage_cfg, "monkey")
    market, detail, quality, input_hash = _prepare_stage_data_cached(
        cfg,
        subset,
        stage_dir,
        skip_validation,
        data_cache=context.get("_prepared_data_cache"),
    )
    selected_row = _select_median_profitable_core_grid_row(
        context.get("limited_core_grid_results"),
        context.get("limited_core_grid_parameters") or {},
    )
    selected_params = _core_grid_params_from_row(
        selected_row,
        context.get("limited_core_grid_parameters") or {},
    )
    test_cfg = apply_dotted_params(cfg, selected_params) if selected_params else copy.deepcopy(cfg)
    core_result = run_research_backtest(test_cfg, market, detail_data=detail, bar_engine_cls=BacktestEngine)
    core_trades = core_result["trades"]
    report_dir = stage_dir if monkey_cfg.get("retain_iteration_reports", True) else None
    results, summary = run_monkey(
        market,
        test_cfg,
        monkey_cfg,
        test_cfg.get("benchmarks", {}),
        report_dir=report_dir,
        detail_data=detail,
        core_trades=core_trades,
    )
    stress_results, stress_summary = _skipped_trade_path_stress()
    summary["trade_path_stress"] = stress_summary
    summary["selected_core_params"] = selected_params
    summary["selected_core_row"] = selected_row.to_dict() if selected_row is not None else {}
    _annotate_stage_data_period(summary, subset, quality)
    _annotate_stage_data_period(stress_summary, subset, quality)
    report_timezone = market_timezone(cfg)
    if bool(monkey_cfg.get("retain_results_csv", _retain_artifact(cfg, "monkey_iteration_results"))):
        write_report_csv(results, stage_dir / "monkey_results.csv", report_timezone, index=False)
    write_report_csv(stress_results, stage_dir / "trade_path_stress_results.csv", report_timezone, index=False)
    write_json(stage_dir / "monkey_summary.json", summary)
    write_json(stage_dir / "trade_path_stress_summary.json", stress_summary)
    return {
        "summary": summary,
        "data_quality": quality,
        "input_hash": input_hash,
        "selected_core_params": selected_params,
        "selected_core_row": summary["selected_core_row"],
        "artifacts": _stage_artifacts(stage_dir),
        "market": market,
        "detail": detail,
    }


def _run_wfa_stage(
    cfg: dict,
    stage_cfg: dict,
    stage_dir: Path,
    skip_validation: bool,
    context: dict,
) -> dict:
    wfa_cfg = _merged_section(cfg, "wfa", stage_cfg)
    wfa_cfg.setdefault("mode", "unanchored")
    wfa_cfg.setdefault("train_months", 48)
    wfa_cfg.setdefault("test_months", 12)
    wfa_cfg.setdefault("step_months", 12)
    wfa_cfg["objective"] = "MAR"
    wfa_cfg.pop("selection_min_trades_per_year", None)
    wfa_cfg["selection_exclusive_min_trades_per_year"] = 50
    wfa_cfg.setdefault("early_exit_min_train_profit_factor", 1.0)
    subset = _stage_subset(
        cfg,
        {"data_window": DEFAULT_WFA_DATA_WINDOW, **stage_cfg},
        "wfa",
    )
    market, detail, quality, input_hash = _prepare_stage_data_cached(
        cfg,
        subset,
        stage_dir,
        skip_validation,
        show_progress=True,
        data_cache=context.get("_prepared_data_cache"),
    )
    results, summary, trades = run_wfa(
        market,
        cfg,
        wfa_cfg,
        cfg.get("benchmarks", {}),
        include_trade_log=True,
        train_grid_dir=stage_dir,
        detail_data=detail,
        input_hash=input_hash,
    )
    report_timezone = market_timezone(cfg)
    write_report_csv(results, stage_dir / "wfa_results.csv", report_timezone, index=False)
    write_report_csv(trades, stage_dir / "wfa_oos_trade_log.csv", report_timezone, index=False)
    initial_balance = float(cfg.get("core", {}).get("initial_balance", 0.0))
    stitched_metrics = calculate_metrics(trades, initial_balance=initial_balance)
    summary["stitched_oos_metrics"] = stitched_metrics
    summary["oos_evaluation_years"] = _wfa_oos_evaluation_years(results)
    summary["required_oos_mar"] = length_adjusted_mar_requirement(summary["oos_evaluation_years"])
    summary["incubation_selected_params"] = _select_incubation_params(results)
    _annotate_stage_data_period(summary, subset, quality)
    summary.update(
        write_equity_report(
            trades,
            stage_dir,
            initial_balance=initial_balance,
            timezone=report_timezone,
            title=f"{cfg.get('campaign_id')} / {cfg.get('variant_id')} staged WFA OOS equity curve",
            write_html=_retain_artifact(cfg, "equity_html"),
        )
    )
    write_json(stage_dir / "wfa_summary.json", summary)
    return {
        "summary": summary,
        "stitched_oos_metrics": stitched_metrics,
        "incubation_selected_params": summary["incubation_selected_params"],
        "data_quality": quality,
        "input_hash": input_hash,
        "artifacts": _stage_artifacts(stage_dir),
        "trades": trades,
        "market": market,
        "detail": detail,
    }


def _run_wfa_oos_monkey(cfg: dict, stage_cfg: dict, stage_dir: Path, context: dict) -> dict:
    trades = _required_context_frame(context, "wfa_trades", "WFA OOS monkey requires walk_forward_analysis trades.")
    market = _market_for_trades(context.get("wfa_market"), trades)
    detail = _market_for_trades(context.get("wfa_detail"), trades) if context.get("wfa_detail") is not None else None
    monkey_cfg = _merged_section(cfg, "monkey", stage_cfg)
    monkey_cfg.setdefault("beat_threshold", 0.80)
    report_dir = stage_dir if monkey_cfg.get("retain_iteration_reports", True) else None
    results, summary = run_monkey(
        market,
        cfg,
        monkey_cfg,
        cfg.get("benchmarks", {}),
        report_dir=report_dir,
        detail_data=detail,
        core_trades=trades,
    )
    stress_results, stress_summary = _skipped_trade_path_stress()
    summary["trade_path_stress"] = stress_summary
    report_timezone = market_timezone(cfg)
    if bool(monkey_cfg.get("retain_results_csv", _retain_artifact(cfg, "monkey_iteration_results"))):
        write_report_csv(results, stage_dir / "wfa_oos_monkey_results.csv", report_timezone, index=False)
    write_report_csv(stress_results, stage_dir / "wfa_oos_trade_path_stress_results.csv", report_timezone, index=False)
    write_json(stage_dir / "wfa_oos_monkey_summary.json", summary)
    write_json(stage_dir / "wfa_oos_trade_path_stress_summary.json", stress_summary)
    return {"summary": summary, "artifacts": _stage_artifacts(stage_dir)}


def _run_wfa_oos_monte_carlo(cfg: dict, stage_cfg: dict, stage_dir: Path, context: dict) -> dict:
    trades = _required_context_frame(context, "wfa_trades", "WFA OOS Monte Carlo requires walk_forward_analysis trades.")
    mc_cfg = {**cfg.get("benchmarks", {}), **copy.deepcopy(cfg.get("monte_carlo", {})), **stage_cfg}
    mc_cfg["_core"] = cfg.get("core", {})
    rules_cfg = _wfa_oos_monte_carlo_rules_config(cfg, stage_cfg)
    rules = PropRules.from_dict(rules_cfg)
    if bool(getattr(rules, "account_lifecycle_enabled", False)):
        mc_cfg["retain_path_trades"] = True
        mc_cfg["retain_path_events"] = True
        if "cluster_losses" not in stage_cfg:
            mc_cfg["cluster_losses"] = False
    retain_path_trades = bool(mc_cfg.get("retain_path_trades", False))
    retain_path_events = bool(mc_cfg.get("retain_path_events", False))
    if retain_path_trades or retain_path_events:
        results, summary, path_trades, path_events = run_monte_carlo_with_audit(trades, mc_cfg, rules)
    else:
        results, summary = run_monte_carlo(trades, mc_cfg, rules)
        path_trades = pd.DataFrame()
        path_events = pd.DataFrame()
    summary["prop_rules_used"] = rules_cfg
    report_timezone = market_timezone(cfg)
    write_report_csv(results, stage_dir / "wfa_oos_monte_carlo_results.csv", report_timezone, index=False)
    write_path_artifacts = bool(mc_cfg.get("write_path_artifacts", _retain_artifact(cfg, "monte_carlo_paths")))
    if retain_path_trades and write_path_artifacts:
        write_report_csv(path_trades, stage_dir / "wfa_oos_monte_carlo_path_trades.csv", report_timezone, index=False)
    if retain_path_events and write_path_artifacts:
        write_report_csv(path_events, stage_dir / "wfa_oos_monte_carlo_path_events.csv", report_timezone, index=False)
    summary["path_artifacts_retained"] = write_path_artifacts
    write_json(stage_dir / "wfa_oos_monte_carlo_summary.json", summary)
    return {"summary": summary, "artifacts": _stage_artifacts(stage_dir)}


def _wfa_oos_monte_carlo_rules_config(cfg: dict, stage_cfg: dict) -> dict:
    top_rules = copy.deepcopy(cfg.get("prop_rules") or {})
    monte_carlo_rules = (cfg.get("monte_carlo") or {}).get("prop_rules")
    stage_rules = stage_cfg.get("prop_rules")
    if top_rules.get("profile_fully_specified") is True:
        declared_hash = str(top_rules.pop("profile_sha256", ""))
        encoded = json.dumps(
            top_rules,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        if not declared_hash or hashlib.sha256(encoded).hexdigest() != declared_hash:
            raise ValueError("fully specified prop-profile hash is missing or stale")
        if isinstance(monte_carlo_rules, dict) or isinstance(stage_rules, dict):
            raise ValueError(
                "a fully specified Studio prop profile cannot be silently overridden by stage settings"
            )
        required = set(PropRules.__dataclass_fields__)
        missing = sorted(required - set(top_rules))
        if missing:
            raise ValueError(
                "fully specified prop profile is missing executable rules: "
                + ", ".join(missing)
            )
        return {key: copy.deepcopy(top_rules[key]) for key in PropRules.__dataclass_fields__}

    rules_cfg = {
        key: top_rules[key]
        for key in (
            "max_contracts",
            "max_best_day_profit_percentage",
            "min_trading_days",
        )
        if key in top_rules
    }
    rules_cfg.update(
        {
            "account_lifecycle_enabled": True,
            "starting_balance": 50000.0,
            "challenge_fee": 98.0,
            "challenge_profit_target_amount": 3000.0,
            "challenge_consistency_limit": 0.50,
            "trailing_drawdown": 2000.0,
            "trailing_drawdown_lock_balance": 52100.0,
            "trailing_drawdown_locked_floor": 50100.0,
            "funded_starting_balance": 50000.0,
            "funded_initial_drawdown_floor": 48000.0,
            "funded_payout_min_profit_day": 150.0,
            "funded_payout_required_profit_days": 5,
            "funded_payout_profit_fraction": 0.50,
            "funded_payout_profit_share": 0.90,
            "funded_payout_max_amount": 2000.0,
            "max_payouts_per_account": 5,
            "profit_target_amount": 3000.0,
            "drawdown_limit_amount": 2000.0,
        }
    )
    if isinstance(monte_carlo_rules, dict):
        _deep_update(rules_cfg, copy.deepcopy(monte_carlo_rules))
    if isinstance(stage_rules, dict):
        _deep_update(rules_cfg, copy.deepcopy(stage_rules))
    drawdown_budget = float(rules_cfg["drawdown_limit_amount"])
    rules_cfg.setdefault("daily_loss_limit", drawdown_budget)
    rules_cfg.setdefault("trailing_drawdown", drawdown_budget)
    return rules_cfg


def _run_incubation_core(
    cfg: dict,
    stage_cfg: dict,
    stage_dir: Path,
    skip_validation: bool,
    context: dict,
) -> dict:
    train_months = int(stage_cfg.get("train_months", 48))
    test_months = int(stage_cfg.get("test_months", 12))
    holdout_after_test_months = int(stage_cfg.get("holdout_after_test_months", 0))
    if train_months <= 0 or test_months <= 0 or holdout_after_test_months < 0:
        raise ValueError(
            "simulated_incubation_core train_months/test_months must be positive and "
            "holdout_after_test_months must be non-negative."
        )

    base_subset = _acceptance_base_subset(cfg, stage_cfg)
    bounded_subset, planned_window = _planned_acceptance_subset(
        base_subset,
        train_months,
        test_months,
        stage_label="simulated_incubation_core",
        holdout_months=holdout_after_test_months,
    )
    market, detail, quality, input_hash = _prepare_stage_data_cached(
        cfg,
        bounded_subset,
        stage_dir,
        skip_validation,
        show_progress=True,
        data_cache=context.get("_prepared_data_cache"),
    )
    window = _resolve_acceptance_window(
        market,
        planned_window,
        train_months,
        test_months,
        stage_label="simulated_incubation_core",
    )
    train = _slice_session_window(market, window["train_start"], window["train_end_exclusive"])
    test = _slice_session_window(market, window["test_start"], window["test_end_exclusive"])
    train_detail = (
        _slice_session_window(detail, window["train_start"], window["train_end_exclusive"])
        if detail is not None
        else None
    )
    test_detail = (
        _slice_session_window(detail, window["test_start"], window["test_end_exclusive"])
        if detail is not None
        else None
    )
    if train.empty or test.empty:
        raise ValueError(
            "simulated_incubation_core requires non-empty in-sample and out-of-sample slices "
            f"for train={_format_acceptance_period(window, 'train')} "
            f"test={_format_acceptance_period(window, 'test')}."
        )

    parameters = _declared_parameter_grid(
        stage_cfg,
        stage_cfg.get("train_selection"),
        cfg.get("wfa"),
        cfg.get("core_grid"),
    )

    selection_cfg = _acceptance_selection_config(cfg, stage_cfg, parameters)
    selection_cfg["data_subset"] = _window_subset(base_subset, window["train_start"], window["train_end_exclusive"])
    selected_params, train_selection_payload = _run_train_selection_grid(
        cfg,
        selection_cfg,
        stage_dir / "train_selection",
        skip_validation,
        train_data=train,
        train_detail=train_detail,
        data_quality=quality,
        input_hash=input_hash,
        parameter_label="simulated_incubation_core.parameters",
        result_prefix="incubation",
    )
    test_cfg = apply_dotted_params(cfg, selected_params) if selected_params else copy.deepcopy(cfg)
    result = run_research_backtest(test_cfg, test, detail_data=test_detail, bar_engine_cls=BacktestEngine)
    trades = result["trades"]
    report_timezone = market_timezone(test_cfg)
    write_report_csv(trades, stage_dir / "trade_log.csv", report_timezone, index=False)
    write_report_csv(result["daily"], stage_dir / "daily_results.csv", report_timezone, index=False)
    metrics = {**result["metrics"], "diagnostics": result.get("diagnostics", {})}
    write_json(stage_dir / "metrics.json", metrics)
    incubation_summary = _acceptance_summary(window, train, test, selected_params, train_selection_payload, result)
    _annotate_stage_data_period(incubation_summary, bounded_subset, quality)
    write_report_csv(
        pd.DataFrame([_acceptance_result_row(incubation_summary)]),
        stage_dir / "incubation_oos_results.csv",
        report_timezone,
        index=False,
    )
    write_json(stage_dir / "incubation_oos_summary.json", incubation_summary)
    write_equity_report(
        trades,
        stage_dir,
        initial_balance=float(test_cfg.get("core", {}).get("initial_balance", 0.0)),
        timezone=report_timezone,
        title=f"{test_cfg.get('campaign_id')} / {test_cfg.get('variant_id')} incubation equity curve",
        write_html=_retain_artifact(test_cfg, "equity_html"),
    )
    return {
        "summary": incubation_summary,
        "metrics": result["metrics"],
        "diagnostics": result.get("diagnostics", {}),
        "selected_params": selected_params,
        "incubation_train_selection": train_selection_payload,
        "data_quality": quality,
        "input_hash": input_hash,
        "artifacts": _stage_artifacts(stage_dir),
        "trades": trades,
        "market": test,
        "detail": test_detail,
        "test_config": test_cfg,
    }


def _run_acceptance_oos(
    cfg: dict,
    stage_cfg: dict,
    stage_dir: Path,
    skip_validation: bool,
    context: dict | None = None,
) -> dict:
    context = context or {}
    train_months = int(stage_cfg.get("train_months", 24))
    test_months = int(stage_cfg.get("test_months", 6))
    if train_months <= 0 or test_months <= 0:
        raise ValueError("acceptance_oos_test train_months and test_months must be greater than zero.")

    base_subset = _acceptance_base_subset(cfg, stage_cfg)
    bounded_subset, planned_window = _planned_acceptance_subset(base_subset, train_months, test_months)
    market, detail, quality, input_hash = _prepare_stage_data_cached(
        cfg,
        bounded_subset,
        stage_dir,
        skip_validation,
        show_progress=True,
        data_cache=context.get("_prepared_data_cache"),
    )
    window = _resolve_acceptance_window(market, planned_window, train_months, test_months)
    train = _slice_session_window(market, window["train_start"], window["train_end_exclusive"])
    test = _slice_session_window(market, window["test_start"], window["test_end_exclusive"])
    train_detail = (
        _slice_session_window(detail, window["train_start"], window["train_end_exclusive"])
        if detail is not None
        else None
    )
    test_detail = (
        _slice_session_window(detail, window["test_start"], window["test_end_exclusive"])
        if detail is not None
        else None
    )
    if train.empty or test.empty:
        raise ValueError(
            "acceptance_oos_test requires non-empty in-sample and out-of-sample slices "
            f"for train={_format_acceptance_period(window, 'train')} "
            f"test={_format_acceptance_period(window, 'test')}."
        )

    parameters = _declared_parameter_grid(
        stage_cfg,
        cfg.get("wfa"),
        cfg.get("core_grid"),
    )

    selection_cfg = _acceptance_selection_config(cfg, stage_cfg, parameters)
    selection_cfg["data_subset"] = _window_subset(base_subset, window["train_start"], window["train_end_exclusive"])
    train_dir = stage_dir / "train_selection"
    selected_params, train_selection_payload = _run_train_selection_grid(
        cfg,
        selection_cfg,
        train_dir,
        skip_validation,
        train_data=train,
        train_detail=train_detail,
        data_quality=quality,
        input_hash=input_hash,
        parameter_label="acceptance_oos_test.parameters",
        result_prefix="acceptance",
    )
    test_cfg = apply_dotted_params(cfg, selected_params) if selected_params else copy.deepcopy(cfg)
    result = run_research_backtest(test_cfg, test, detail_data=test_detail, bar_engine_cls=BacktestEngine)
    trades = result["trades"]
    report_timezone = market_timezone(test_cfg)
    write_report_csv(trades, stage_dir / "trade_log.csv", report_timezone, index=False)
    write_report_csv(result["daily"], stage_dir / "daily_results.csv", report_timezone, index=False)
    metrics = {**result["metrics"], "diagnostics": result.get("diagnostics", {})}
    write_json(stage_dir / "metrics.json", metrics)
    acceptance_summary = _acceptance_summary(window, train, test, selected_params, train_selection_payload, result)
    _annotate_stage_data_period(acceptance_summary, bounded_subset, quality)
    write_report_csv(
        pd.DataFrame([_acceptance_result_row(acceptance_summary)]),
        stage_dir / "acceptance_oos_results.csv",
        report_timezone,
        index=False,
    )
    write_json(stage_dir / "acceptance_oos_summary.json", acceptance_summary)
    write_equity_report(
        trades,
        stage_dir,
        initial_balance=float(test_cfg.get("core", {}).get("initial_balance", 0.0)),
        timezone=report_timezone,
        title=f"{test_cfg.get('campaign_id')} / {test_cfg.get('variant_id')} acceptance OOS equity curve",
        write_html=_retain_artifact(test_cfg, "equity_html"),
    )
    return {
        "summary": acceptance_summary,
        "metrics": result["metrics"],
        "diagnostics": result.get("diagnostics", {}),
        "selected_params": selected_params,
        "acceptance_train_selection": train_selection_payload,
        "data_quality": quality,
        "input_hash": input_hash,
        "artifacts": _stage_artifacts(stage_dir),
        "trades": trades,
        "market": test,
        "detail": test_detail,
    }


def _run_incubation_monkey(cfg: dict, stage_cfg: dict, stage_dir: Path, context: dict) -> dict:
    trades = _required_context_frame(context, "incubation_trades", "Incubation monkey requires simulated_incubation_core trades.")
    market = context.get("incubation_market")
    if market is None or market.empty:
        raise ValueError("Incubation monkey requires simulated_incubation_core market data.")
    detail = context.get("incubation_detail")
    test_cfg = context.get("incubation_config") or cfg
    monkey_cfg = _merged_section(cfg, "monkey", stage_cfg)
    monkey_cfg.setdefault("beat_threshold", 0.80)
    report_dir = stage_dir if monkey_cfg.get("retain_iteration_reports", True) else None
    results, summary = run_monkey(
        market,
        test_cfg,
        monkey_cfg,
        test_cfg.get("benchmarks", {}),
        report_dir=report_dir,
        detail_data=detail,
        core_trades=trades,
    )
    stress_results, stress_summary = _skipped_trade_path_stress()
    summary["trade_path_stress"] = stress_summary
    report_timezone = market_timezone(cfg)
    if bool(monkey_cfg.get("retain_results_csv", _retain_artifact(cfg, "monkey_iteration_results"))):
        write_report_csv(results, stage_dir / "incubation_monkey_results.csv", report_timezone, index=False)
    write_report_csv(stress_results, stage_dir / "incubation_trade_path_stress_results.csv", report_timezone, index=False)
    write_json(stage_dir / "incubation_monkey_summary.json", summary)
    write_json(stage_dir / "incubation_trade_path_stress_summary.json", stress_summary)
    return {"summary": summary, "artifacts": _stage_artifacts(stage_dir)}


def _prepare_stage_data_cached(
    cfg: dict,
    subset: dict | None,
    stage_dir: Path,
    skip_validation: bool,
    show_progress: bool = False,
    data_cache: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame | None, dict, str]:
    kwargs = {"show_progress": show_progress}
    code = getattr(_prepare_stage_data, "__code__", None)
    if data_cache is not None and code is not None and "data_cache" in code.co_varnames:
        kwargs["data_cache"] = data_cache
    return _prepare_stage_data(cfg, subset, stage_dir, skip_validation, **kwargs)


def _prepare_stage_data(
    cfg: dict,
    subset: dict | None,
    stage_dir: Path,
    skip_validation: bool,
    show_progress: bool = False,
    data_cache: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame | None, dict, str]:
    timeframe = config_timeframe(cfg)
    output_dir = None if skip_validation else stage_dir / "validation"
    cache_key = _prepared_data_cache_key(cfg, subset, timeframe) if output_dir is None and data_cache is not None else None
    if cache_key and cache_key in data_cache:
        market, detail, quality, input_hash = data_cache[cache_key]
        quality = {
            **quality,
            "prepared_data_cache": {
                "enabled": True,
                "hit": True,
                "key": cache_key,
            },
        }
        return market, detail, quality, input_hash

    started = time.perf_counter()
    market, quality, execution_data = prepare_data(
        cfg["data"],
        output_dir,
        subset,
        timeframe=timeframe,
        include_execution_data=True,
        show_progress=show_progress,
    )
    detail = execution_data if timeframe != "1m" else None
    input_hash = data_source_hash(cfg["data"], subset)
    quality = {
        **quality,
        "prepare_data_duration_seconds": round(time.perf_counter() - started, 6),
        "prepared_data_cache": {
            "enabled": cache_key is not None,
            "hit": False,
            "key": cache_key,
        },
    }
    if cache_key:
        data_cache[cache_key] = (market, detail, quality, input_hash)
    return market, detail, quality, input_hash


def _prepared_data_cache_key(cfg: dict, subset: dict | None, timeframe: str) -> str:
    return object_sha256(
        {
            "data": cfg.get("data", {}),
            "subset": subset or {},
            "timeframe": timeframe,
        }
    )


def evaluate_criteria(payload: dict, criteria: list[dict]) -> list[dict]:
    out = []
    for item in criteria:
        metric = item["metric"]
        actual = _lookup(payload, metric)
        passed = True
        expected = {}
        if "dynamic_min" in item:
            value = _dynamic_minimum(payload, item)
            expected["min"] = value
            expected["dynamic_min"] = item["dynamic_min"]
            span_metric = item.get("span_metric")
            if span_metric:
                expected["span_metric"] = span_metric
                expected["span_years"] = _lookup(payload, span_metric)
            passed = passed and _numeric(actual) >= value
        if "min" in item:
            expected["min"] = item["min"]
            passed = passed and _numeric(actual) >= float(item["min"])
        if "exclusive_min" in item:
            expected["exclusive_min"] = item["exclusive_min"]
            passed = passed and _numeric(actual) > float(item["exclusive_min"])
        if "max" in item:
            expected["max"] = item["max"]
            passed = passed and _numeric(actual) <= float(item["max"])
        if "equals" in item:
            expected["equals"] = item["equals"]
            passed = passed and actual == item["equals"]
        if item.get("valid_parameter_combination_count"):
            expected["valid_parameter_combination_count"] = "1 fixed combo or 8-120 tunable combos"
            passed = passed and _valid_parameter_combination_count(actual)
        out.append(
            {
                "metric": metric,
                "actual": actual,
                "expected": expected,
                "passed": bool(passed),
            }
        )
    return out


def _valid_parameter_combination_count(value) -> bool:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(numeric) or not numeric.is_integer():
        return False
    count = int(numeric)
    return count == 1 or 8 <= count <= 120


def length_adjusted_mar_requirement(years: float | int | None) -> float:
    if years is None:
        return 1.5
    years = float(years)
    if not math.isfinite(years) or years <= 0:
        return 1.5
    exponent = math.log(3.0) / math.log(5.0)
    required = 1.5 * ((years / 3.0) ** -exponent)
    return max(0.50, min(1.50, required))


def _dynamic_minimum(payload: dict, item: dict) -> float:
    name = item["dynamic_min"]
    if name == "length_adjusted_mar":
        years = _lookup(payload, item.get("span_metric", "summary.oos_evaluation_years"))
        return length_adjusted_mar_requirement(years)
    raise ValueError(f"Unsupported dynamic minimum: {name}")


def _criteria_for_stage(stage_name: str, stage_cfg: dict) -> list[dict]:
    if stage_name in DEFAULT_STAGE_CRITERIA:
        return copy.deepcopy(DEFAULT_STAGE_CRITERIA[stage_name])
    configured = stage_cfg.get("criteria")
    if configured:
        if isinstance(configured, dict):
            return [{"metric": metric, **rule} for metric, rule in configured.items()]
        return list(configured)
    return copy.deepcopy(DEFAULT_STAGE_CRITERIA.get(stage_name, []))


def _stage_order(campaign_tests: dict) -> list[str]:
    configured = campaign_tests.get("stage_order")
    if not configured:
        return list(DEFAULT_STAGE_ORDER)
    order = list(configured)
    if ACCEPTANCE_STAGE in order:
        return order
    acceptance_cfg = campaign_tests.get(ACCEPTANCE_STAGE) or {}
    if acceptance_cfg.get("enabled", True) is False:
        return order
    return [*order, ACCEPTANCE_STAGE]


def _stage_config(campaign_tests: dict, stage_name: str) -> dict:
    return copy.deepcopy(campaign_tests.get(stage_name) or {})


def _data_source_name(data_cfg: dict) -> str | None:
    if data_cfg.get("source"):
        return str(data_cfg["source"])
    if data_cfg.get("raw_dir"):
        return "databento_dbn"
    if data_cfg.get("raw_parquet"):
        return "parquet"
    if data_cfg.get("raw_csv"):
        return "csv"
    return None


def _acceptance_base_subset(cfg: dict, stage_cfg: dict) -> dict:
    if stage_cfg.get("data_subset"):
        return dict(stage_cfg["data_subset"])
    return dict((cfg.get("core") or {}).get("data_subset") or (cfg.get("data") or {}).get("data_subset") or {})


def _planned_acceptance_subset(
    base_subset: dict,
    train_months: int,
    test_months: int,
    *,
    stage_label: str = "acceptance_oos_test",
    holdout_months: int = 0,
) -> tuple[dict | None, dict | None]:
    end = _subset_end_date(base_subset)
    if end is None:
        return (dict(base_subset) if base_subset else None), None
    if holdout_months < 0:
        raise ValueError(f"{stage_label} holdout_months must be non-negative.")
    window_end = end
    if holdout_months:
        reserved_holdout_start = (end - pd.DateOffset(months=holdout_months)).normalize()
        window_end = reserved_holdout_start - pd.Timedelta(days=1)
    window = _acceptance_window_from_end(window_end, train_months, test_months)
    start = _subset_start_date(base_subset)
    if start is not None and start > window["train_start"]:
        raise ValueError(
            f"{stage_label} requires the configured data range to cover the full "
            f"{train_months}-month in-sample window starting {window['train_start'].date().isoformat()}; "
            f"configured start_date is {start.date().isoformat()}."
        )
    bounded = dict(base_subset)
    bounded["start_date"] = window["train_start"].date().isoformat()
    bounded["end_date"] = window["test_end"].date().isoformat()
    return bounded, window


def _resolve_acceptance_window(
    market: pd.DataFrame,
    planned_window: dict | None,
    train_months: int,
    test_months: int,
    *,
    stage_label: str = "acceptance_oos_test",
) -> dict:
    if planned_window is not None:
        return planned_window
    if market.empty or "session_date" not in market.columns:
        raise ValueError(f"{stage_label} cannot infer latest data date from an empty market slice.")
    sessions = pd.to_datetime(market["session_date"], errors="coerce").dropna()
    if sessions.empty:
        raise ValueError(f"{stage_label} cannot infer latest data date from session_date.")
    return _acceptance_window_from_end(pd.Timestamp(sessions.max()).normalize(), train_months, test_months)


def _acceptance_window_from_end(end_date, train_months: int, test_months: int) -> dict:
    test_end = pd.Timestamp(end_date).normalize()
    test_end_exclusive = test_end + pd.Timedelta(days=1)
    test_start = (test_end - pd.DateOffset(months=test_months)).normalize()
    train_start = (test_start - pd.DateOffset(months=train_months)).normalize()
    return {
        "train_months": train_months,
        "test_months": test_months,
        "train_start": train_start,
        "train_end_exclusive": test_start,
        "train_end": test_start - pd.Timedelta(days=1),
        "test_start": test_start,
        "test_end": test_end,
        "test_end_exclusive": test_end_exclusive,
    }


def _subset_start_date(subset: dict) -> pd.Timestamp | None:
    if subset.get("start_date"):
        return pd.Timestamp(subset["start_date"]).normalize()
    if subset.get("start_timestamp"):
        return pd.Timestamp(subset["start_timestamp"]).normalize()
    return None


def _subset_end_date(subset: dict) -> pd.Timestamp | None:
    if subset.get("end_date"):
        return pd.Timestamp(subset["end_date"]).normalize()
    if subset.get("end_timestamp"):
        return pd.Timestamp(subset["end_timestamp"]).normalize()
    return None


def _slice_session_window(data: pd.DataFrame | None, start, end_exclusive) -> pd.DataFrame:
    if data is None or data.empty:
        return pd.DataFrame()
    sessions = pd.to_datetime(data["session_date"], errors="coerce")
    mask = (sessions >= pd.Timestamp(start).normalize()) & (sessions < pd.Timestamp(end_exclusive).normalize())
    return data[mask].copy().reset_index(drop=True)


def _acceptance_selection_config(cfg: dict, stage_cfg: dict, parameters: dict) -> dict:
    out = copy.deepcopy(stage_cfg.get("train_selection") or {})
    for key in [
        "parallel",
        "retain_iteration_reports",
        "selection_min_profit_factor",
        "selection_min_total_trades",
        "selection_min_trades_per_year",
        "selection_exclusive_min_trades_per_year",
    ]:
        if key in stage_cfg and key not in out:
            out[key] = copy.deepcopy(stage_cfg[key])
    if "selection_min_trades_per_year" not in out and "selection_exclusive_min_trades_per_year" not in out:
        if (cfg.get("wfa") or {}).get("selection_min_trades_per_year") is not None:
            out["selection_min_trades_per_year"] = (cfg.get("wfa") or {})["selection_min_trades_per_year"]
        elif (cfg.get("benchmarks") or {}).get("min_trades_per_year") is not None:
            out["selection_min_trades_per_year"] = (cfg.get("benchmarks") or {})["min_trades_per_year"]
        else:
            out["selection_exclusive_min_trades_per_year"] = 50
    out["objective"] = "MAR"
    out.pop("selection_min_trades_per_year", None)
    out["selection_exclusive_min_trades_per_year"] = 50
    out["parameters"] = copy.deepcopy(parameters)
    out.setdefault("retain_iteration_reports", False)
    return out


def _window_subset(base_subset: dict, start, end_exclusive) -> dict:
    out = {
        key: copy.deepcopy(value)
        for key, value in base_subset.items()
        if key not in {"start_date", "end_date", "start_timestamp", "end_timestamp"}
    }
    out["start_date"] = pd.Timestamp(start).date().isoformat()
    out["end_date"] = (pd.Timestamp(end_exclusive).normalize() - pd.Timedelta(days=1)).date().isoformat()
    return out


def _acceptance_summary(
    window: dict,
    train: pd.DataFrame,
    test: pd.DataFrame,
    selected_params: dict,
    train_selection_payload: dict,
    result: dict,
) -> dict:
    selected_row = train_selection_payload.get("selected_row", {})
    return {
        "selection_objective": "MAR",
        "train_months": int(window["train_months"]),
        "test_months": int(window["test_months"]),
        "train_start": window["train_start"].date().isoformat(),
        "train_end": window["train_end"].date().isoformat(),
        "test_start": window["test_start"].date().isoformat(),
        "test_end": window["test_end"].date().isoformat(),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "selected_params": selected_params,
        "train_selected_metrics": {
            key: selected_row.get(key)
            for key in [
                "run_id",
                "total_trades",
                "trades_per_year",
                "net_profit",
                "profit_factor",
                "expectancy_r",
                "max_drawdown",
                "max_drawdown_pct",
                "cagr",
                "mar",
                "win_rate",
                "apex_rule_violations",
            ]
            if key in selected_row
        },
        "metrics": result["metrics"],
        "diagnostics": result.get("diagnostics", {}),
        "oos_trades": int(len(result.get("trades", pd.DataFrame()))),
    }


def _acceptance_result_row(summary: dict) -> dict:
    row = {
        "selection_objective": summary["selection_objective"],
        "train_start": summary["train_start"],
        "train_end": summary["train_end"],
        "test_start": summary["test_start"],
        "test_end": summary["test_end"],
        "train_rows": summary["train_rows"],
        "test_rows": summary["test_rows"],
        "selected_params": summary["selected_params"],
    }
    row.update({f"train_{key}": value for key, value in summary.get("train_selected_metrics", {}).items()})
    row.update({f"test_{key}": value for key, value in summary.get("metrics", {}).items()})
    for key, value in summary.get("selected_params", {}).items():
        row[key] = value
    return row


def _format_acceptance_period(window: dict, prefix: str) -> str:
    return f"{window[f'{prefix}_start'].date().isoformat()}->{window[f'{prefix}_end'].date().isoformat()}"


def _retain_artifact(cfg: dict, key: str) -> bool:
    retention = cfg.get("artifact_retention") or {}
    return bool(retention.get(key, False))


def _merged_section(cfg: dict, section: str, stage_cfg: dict) -> dict:
    out = copy.deepcopy(cfg.get(section, {}))
    overrides = {
        key: value
        for key, value in stage_cfg.items()
        if key
        not in {
            "criteria",
            "data_subset",
            "data_window",
            "enabled",
            "selected_params",
            "train_selection",
        }
    }
    _deep_update(out, overrides)
    return out


def _deep_update(target: dict, updates: dict) -> dict:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value
    return target


def _stage_subset(cfg: dict, stage_cfg: dict, fallback_section: str) -> dict | None:
    if stage_cfg.get("data_subset"):
        return dict(stage_cfg["data_subset"])
    fallback = _stage_base_subset(cfg, fallback_section)
    window = stage_cfg.get("data_window")
    if window:
        return _subset_from_window(fallback, window)
    return fallback or None


def _stage_base_subset(cfg: dict, fallback_section: str) -> dict:
    for section in (fallback_section, "core", "data"):
        subset = (cfg.get(section) or {}).get("data_subset")
        if subset:
            return dict(subset)
    return {}


def _subset_from_window(base_subset: dict, window: dict) -> dict:
    if not base_subset.get("end_date") and not base_subset.get("start_date"):
        return base_subset
    mode = str(window.get("mode", "")).lower()
    months = int(window.get("months", 18))
    start = pd.Timestamp(base_subset.get("start_date")) if base_subset.get("start_date") else None
    end = pd.Timestamp(base_subset.get("end_date")) if base_subset.get("end_date") else None
    out = dict(base_subset)
    if mode == "first_months" and start is not None:
        first_end = start + pd.DateOffset(months=months)
        out["end_date"] = min(first_end, end).date().isoformat() if end is not None else first_end.date().isoformat()
    elif mode == "first_fraction" and start is not None and end is not None:
        fraction = _bounded_fraction(window.get("fraction", 1.0))
        days = max(int((end - start).days) + 1, 1)
        selected_days = max(1, int(math.floor(days * fraction)))
        out["end_date"] = min(start + pd.Timedelta(days=selected_days - 1), end).date().isoformat()
    elif mode == "exclude_last_months" and end is not None:
        out["end_date"] = (end - pd.DateOffset(months=months)).date().isoformat()
    elif mode == "last_months" and end is not None:
        out["start_date"] = (end - pd.DateOffset(months=months)).date().isoformat()
    elif mode == "random_months" and start is not None and end is not None:
        seed = int(window.get("seed", 1))
        candidates = pd.date_range(start, end - pd.DateOffset(months=months), freq="MS")
        candidates = _exclude_avoid_ranges(candidates, window.get("avoid_ranges", []), months)
        if len(candidates):
            chosen = candidates[seed % len(candidates)]
            out["start_date"] = chosen.date().isoformat()
            out["end_date"] = (chosen + pd.DateOffset(months=months)).date().isoformat()
    elif mode == "random_fraction" and start is not None and end is not None:
        fraction = _bounded_fraction(window.get("fraction", 0.10))
        avoid_last_fraction = max(0.0, min(1.0, float(window.get("avoid_last_fraction", 0.0))))
        days = max(int((end - start).days) + 1, 1)
        selected_days = max(1, int(math.floor(days * fraction)))
        avoid_last_days = int(math.ceil(days * avoid_last_fraction))
        latest_allowed_end = end - pd.Timedelta(days=avoid_last_days)
        latest_start = latest_allowed_end - pd.Timedelta(days=selected_days - 1)
        if latest_start < start:
            raise ValueError("random_fraction data_window cannot fit inside the configured data range.")
        candidates = pd.date_range(start, latest_start, freq="D")
        candidates = _exclude_avoid_day_ranges(candidates, window.get("avoid_ranges", []), selected_days)
        if not len(candidates):
            raise ValueError("random_fraction data_window has no candidates after avoid_ranges exclusions.")
        chosen = random.Random(int(window.get("seed", 1))).choice(list(candidates))
        out["start_date"] = chosen.date().isoformat()
        out["end_date"] = (chosen + pd.Timedelta(days=selected_days - 1)).date().isoformat()
    elif mode == "before_sequential_holdouts" and end is not None:
        incubation_months = int(window.get("incubation_test_months", 12))
        acceptance_months = int(window.get("acceptance_test_months", 6))
        if incubation_months <= 0 or acceptance_months <= 0:
            raise ValueError(
                "before_sequential_holdouts requires positive incubation_test_months "
                "and acceptance_test_months."
            )
        acceptance_start = (end - pd.DateOffset(months=acceptance_months)).normalize()
        incubation_end = acceptance_start - pd.Timedelta(days=1)
        incubation_start = (
            incubation_end - pd.DateOffset(months=incubation_months)
        ).normalize()
        out["end_date"] = (incubation_start - pd.Timedelta(days=1)).date().isoformat()
    return out


def _bounded_fraction(value) -> float:
    fraction = float(value)
    if not math.isfinite(fraction) or fraction <= 0:
        raise ValueError("data_window fraction must be greater than zero.")
    return min(fraction, 1.0)


def _exclude_avoid_day_ranges(candidates: pd.DatetimeIndex, avoid_ranges: list[dict], days: int) -> pd.DatetimeIndex:
    if not avoid_ranges or candidates.empty:
        return candidates
    keep = []
    for candidate in candidates:
        candidate_end = candidate + pd.Timedelta(days=max(int(days) - 1, 0))
        overlaps = False
        for item in avoid_ranges:
            start = pd.Timestamp(item["start_date"]).normalize()
            end = pd.Timestamp(item["end_date"]).normalize()
            if candidate <= end and candidate_end >= start:
                overlaps = True
                break
        keep.append(not overlaps)
    return candidates[keep]


def _exclude_avoid_ranges(candidates: pd.DatetimeIndex, avoid_ranges: list[dict], months: int) -> pd.DatetimeIndex:
    if not avoid_ranges or candidates.empty:
        return candidates
    keep = []
    for candidate in candidates:
        candidate_end = candidate + pd.DateOffset(months=months)
        overlaps = False
        for item in avoid_ranges:
            start = pd.Timestamp(item["start_date"])
            end = pd.Timestamp(item["end_date"])
            if candidate < end and candidate_end > start:
                overlaps = True
                break
        keep.append(not overlaps)
    return candidates[keep]


def _select_incubation_params(wfa_results: pd.DataFrame) -> dict:
    if wfa_results.empty or "selected_params" not in wfa_results.columns:
        return {}
    candidates = wfa_results.copy()
    if "early_exit" in candidates.columns:
        candidates = candidates[~candidates["early_exit"].fillna(False)]
    if candidates.empty:
        return {}
    sort_columns = [column for column in ["test_profit_factor", "test_mar", "test_net_profit"] if column in candidates.columns]
    if not sort_columns:
        row = candidates.iloc[-1]
    else:
        row = candidates.sort_values(sort_columns, ascending=[False] * len(sort_columns), na_position="last").iloc[0]
    params = row.get("selected_params", {})
    return params if isinstance(params, dict) else {}


def _run_incubation_train_selection(
    cfg: dict,
    selection_cfg: dict,
    train_dir: Path,
    skip_validation: bool,
    data_cache: dict | None = None,
) -> tuple[dict, dict]:
    selection_cfg = copy.deepcopy(selection_cfg)
    selection_cfg["objective"] = "MAR"
    selection_cfg.pop("selection_min_trades_per_year", None)
    selection_cfg["selection_exclusive_min_trades_per_year"] = 50
    train_subset = selection_cfg.get("data_subset") or {}
    if not train_subset:
        raise ValueError("simulated_incubation_core.train_selection.data_subset is required.")
    market, detail, quality, input_hash = _prepare_stage_data_cached(
        cfg,
        dict(train_subset),
        train_dir,
        skip_validation,
        show_progress=True,
        data_cache=data_cache,
    )
    return _run_train_selection_grid(
        cfg,
        selection_cfg,
        train_dir,
        skip_validation,
        train_data=market,
        train_detail=detail,
        data_quality=quality,
        input_hash=input_hash,
        parameter_label="simulated_incubation_core.train_selection.parameters",
        result_prefix="incubation",
    )


def _run_train_selection_grid(
    cfg: dict,
    selection_cfg: dict,
    train_dir: Path,
    skip_validation: bool,
    *,
    train_data: pd.DataFrame,
    train_detail: pd.DataFrame | None,
    data_quality: dict,
    input_hash: str,
    parameter_label: str,
    result_prefix: str,
) -> tuple[dict, dict]:
    train_dir.mkdir(parents=True, exist_ok=True)
    train_subset = selection_cfg.get("data_subset") or {}
    grid_cfg = copy.deepcopy(cfg.get("core_grid", {}))
    _deep_update(grid_cfg, {key: value for key, value in selection_cfg.items() if key != "data_subset"})
    parameters = _declared_parameter_grid(
        selection_cfg,
        cfg.get("wfa"),
        cfg.get("core_grid"),
    )
    grid_cfg["parameters"] = copy.deepcopy(parameters)
    grid_cfg["data_subset"] = dict(train_subset)
    grid_cfg.setdefault("retain_iteration_reports", False)
    results, summary = run_core_grid(
        train_data,
        cfg,
        grid_cfg,
        cfg.get("benchmarks", {}),
        report_dir=train_dir if grid_cfg.get("retain_iteration_reports", False) else None,
        parameter_label=parameter_label,
        detail_data=train_detail,
    )
    selected_row = _select_core_grid_row(results, parameters, selection_cfg)
    if selected_row is None:
        raise ValueError("train selection found no parameter rows satisfying the configured selection filters.")
    selected_params = _core_grid_params_from_row(selected_row, parameters)
    report_timezone = market_timezone(cfg)
    write_report_csv(results, train_dir / f"{result_prefix}_train_grid_results.csv", report_timezone, index=False)
    summary["selected_params"] = selected_params
    summary["selected_row"] = selected_row.to_dict() if selected_row is not None else {}
    _annotate_stage_data_period(summary, train_subset, data_quality)
    write_json(train_dir / f"{result_prefix}_train_grid_summary.json", summary)
    write_json(train_dir / f"{result_prefix}_selected_params.json", selected_params)
    return selected_params, {
        "summary": summary,
        "selected_params": selected_params,
        "selected_row": summary["selected_row"],
        "data_quality": data_quality,
        "input_hash": input_hash,
        "artifacts": _stage_artifacts(train_dir),
    }


def _declared_parameter_grid(*containers: object) -> dict:
    """Resolve the first explicitly declared grid, preserving an empty fixed grid."""

    for container in containers:
        if not isinstance(container, dict) or "parameters" not in container:
            continue
        parameters = container["parameters"]
        if not isinstance(parameters, dict):
            raise ValueError("declared parameters must be a mapping; use {} for one fixed configuration.")
        return copy.deepcopy(parameters)
    return {}


def _select_core_grid_params(results: pd.DataFrame, parameters: dict, selection_cfg: dict) -> dict:
    selected_row = _select_core_grid_row(results, parameters, selection_cfg)
    if selected_row is None:
        raise ValueError("core grid selection found no parameter rows satisfying the configured selection filters.")
    return _core_grid_params_from_row(selected_row, parameters)


def _select_core_grid_row(results: pd.DataFrame, parameters: dict, selection_cfg: dict):
    if results.empty:
        return None
    candidates = results.copy()
    min_total_trades = selection_cfg.get("selection_min_total_trades")
    if min_total_trades is not None:
        if "total_trades" not in candidates.columns:
            return None
        candidates = candidates[pd.to_numeric(candidates["total_trades"], errors="coerce") >= float(min_total_trades)]
        if candidates.empty:
            return None
    min_trades_per_year = selection_cfg.get("selection_min_trades_per_year")
    if min_trades_per_year is not None:
        if "trades_per_year" not in candidates.columns:
            return None
        candidates = candidates[pd.to_numeric(candidates["trades_per_year"], errors="coerce") >= float(min_trades_per_year)]
        if candidates.empty:
            return None
    exclusive_min_trades_per_year = selection_cfg.get("selection_exclusive_min_trades_per_year")
    if exclusive_min_trades_per_year is not None:
        if "trades_per_year" not in candidates.columns:
            return None
        candidates = candidates[
            pd.to_numeric(candidates["trades_per_year"], errors="coerce")
            > float(exclusive_min_trades_per_year)
        ]
        if candidates.empty:
            return None
    objective = str(selection_cfg.get("objective", "MAR")).lower()
    objective_columns = {
        "mar": "mar",
        "profit_factor": "profit_factor",
        "pf": "profit_factor",
        "net_profit": "net_profit",
        "expectancy_r": "expectancy_r",
    }
    objective_column = objective_columns.get(objective, objective)
    sort_columns = [column for column in [objective_column, "profit_factor", "net_profit"] if column in candidates.columns]
    if sort_columns:
        return candidates.sort_values(sort_columns, ascending=[False] * len(sort_columns), na_position="last").iloc[0]
    return candidates.iloc[0]


def _core_grid_params_from_row(row, parameters: dict) -> dict:
    if row is None:
        return {}
    return {key: row[key] for key in parameters if key in row and not pd.isna(row[key])}


def _select_median_profitable_core_grid_row(results: pd.DataFrame | None, parameters: dict):
    if results is None or results.empty:
        raise ValueError("limited_monkey_test requires limited_core_grid_test results.")
    if "net_profit" not in results.columns:
        raise ValueError("limited_monkey_test requires net_profit in limited_core_grid_test results.")
    candidates = results.copy()
    net_profit = pd.to_numeric(candidates["net_profit"], errors="coerce")
    if "profitable" in candidates.columns:
        profitable = candidates[candidates["profitable"].fillna(False).astype(bool)].copy()
    else:
        profitable = candidates[net_profit > 0].copy()
    if profitable.empty:
        raise ValueError("limited_monkey_test requires at least one profitable limited core-grid row.")
    median_net_profit = float(pd.to_numeric(profitable["net_profit"], errors="coerce").median())
    profitable["_median_net_profit_distance"] = (
        pd.to_numeric(profitable["net_profit"], errors="coerce") - median_net_profit
    ).abs()
    sort_columns = ["_median_net_profit_distance"]
    if "run_id" in profitable.columns:
        sort_columns.append("run_id")
    row = profitable.sort_values(sort_columns, kind="stable").iloc[0].drop(labels=["_median_net_profit_distance"])
    return row


def _wfa_oos_evaluation_years(wfa_results: pd.DataFrame) -> float:
    if wfa_results.empty or not {"test_start", "test_end"}.issubset(wfa_results.columns):
        return 0.0
    starts = pd.to_datetime(wfa_results["test_start"], errors="coerce")
    ends = pd.to_datetime(wfa_results["test_end"], errors="coerce")
    if starts.dropna().empty or ends.dropna().empty:
        return 0.0
    elapsed_days = max((ends.max() - starts.min()).total_seconds() / 86400.0, 1.0)
    return float(elapsed_days / 365.25)


def _required_context_frame(context: dict, key: str, message: str) -> pd.DataFrame:
    frame = context.get(key)
    if frame is None or frame.empty:
        raise ValueError(message)
    return frame


def _market_for_trades(market: pd.DataFrame | None, trades: pd.DataFrame) -> pd.DataFrame:
    if market is None or market.empty or trades.empty:
        return market if market is not None else pd.DataFrame()
    start = pd.to_datetime(trades["entry_timestamp"], utc=True).min().tz_convert(None)
    end = pd.to_datetime(trades["exit_timestamp"], utc=True).max().tz_convert(None)
    naive = market["timestamp"].dt.tz_localize(None)
    return market[(naive >= start) & (naive <= end)].copy()


def _stage_artifacts(stage_dir: Path) -> list[str]:
    files = []
    for path in sorted(stage_dir.rglob("*")):
        if path.is_file():
            files.append(str(path))
    return files


def _lookup(payload: dict, path: str):
    current: Any = payload
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _numeric(value) -> float:
    if value is None or pd.isna(value):
        return float("-inf")
    return float(value)


def _skipped_stage(stage_name: str, reason: str) -> dict:
    return {
        "stage": stage_name,
        "label": STAGE_LABELS.get(stage_name, stage_name),
        "status": "skipped",
        "passed": False,
        "skip_reason": reason,
        "criteria": [],
    }


def _error_stage(stage_name: str, exc: Exception) -> dict:
    criteria = evaluate_criteria(
        {"stage": stage_name, "error": str(exc)},
        copy.deepcopy(DEFAULT_STAGE_CRITERIA.get(stage_name, [])),
    )
    return {
        "stage": stage_name,
        "label": STAGE_LABELS.get(stage_name, stage_name),
        "status": "error",
        "passed": False,
        "error": str(exc),
        "criteria": criteria,
    }


def _markdown_summary(summary: dict) -> str:
    lines = [
        f"# Campaign Test Summary",
        "",
        f"- Campaign: `{summary.get('campaign_id')}`",
        f"- Variant: `{summary.get('variant_id')}`",
        f"- Timeframe: `{summary.get('timeframe')}`",
        f"- Research verdict: `{summary.get('research_verdict', 'NEEDS MANUAL REVIEW')}`",
        f"- Overall passed: `{summary.get('passed')}`",
        "",
        "| Stage | Status | Failed Criteria |",
        "|---|---:|---|",
    ]
    for stage in summary.get("stages", []):
        failures = [
            f"{item['metric']} actual={item.get('actual')} expected={item.get('expected')}"
            for item in stage.get("criteria", [])
            if not item.get("passed")
        ]
        if stage.get("error"):
            failures.append(stage["error"])
        if stage.get("skip_reason"):
            failures.append(stage["skip_reason"])
        lines.append(
            f"| {stage.get('label', stage.get('stage'))} | {stage.get('status')} | "
            f"{'<br>'.join(failures) if failures else ''} |"
        )
    lines.append("")
    return "\n".join(lines)
