from __future__ import annotations

import copy
from datetime import datetime
import math
import os
from pathlib import Path
import time
from typing import Any

import pandas as pd
import yaml

from propstack.backtest.engine import BacktestEngine
from propstack.backtest.equity_report import write_equity_report
from propstack.backtest.metrics import calculate_metrics
from propstack.data.pipeline import prepare_data
from propstack.data.source import data_source_hash
from propstack.prop.rules import PropRules
from propstack.research.core_grid import run_core_grid
from propstack.research.monkey import run_monkey
from propstack.research.monte_carlo import run_monte_carlo, run_monte_carlo_with_audit
from propstack.research.wfa import run_wfa
from propstack.utils.config import config_timeframe, load_yaml, variant_root, write_json
from propstack.utils.hashing import object_sha256
from propstack.utils.params import apply_dotted_params
from propstack.utils.reports import market_timezone, write_report_csv


ACCEPTANCE_STAGE = "acceptance_oos_test"

PRE_ACCEPTANCE_STAGE_ORDER = [
    "limited_core_grid_test",
    "limited_monkey_test",
    "walk_forward_analysis",
    "wfa_oos_monkey_test",
    "wfa_oos_monte_carlo",
    "simulated_incubation_core",
    "simulated_incubation_monkey",
]

DEFAULT_STAGE_ORDER = [*PRE_ACCEPTANCE_STAGE_ORDER, ACCEPTANCE_STAGE]

DEFAULT_STAGE_CRITERIA = {
    "limited_core_grid_test": [
        {"metric": "summary.total_combinations_tested", "min": 100},
        {"metric": "summary.percentage_profitable_iterations", "min": 0.70},
        {"metric": "summary.apex_rule_violating_iterations", "max": 0},
    ],
    "limited_monkey_test": [
        {"metric": "summary.core_beats_monkey_net_profit_rate", "min": 0.90},
        {"metric": "summary.core_beats_monkey_max_drawdown_rate", "min": 0.90},
        {"metric": "summary.core_metrics.apex_rule_violations", "max": 0},
    ],
    "walk_forward_analysis": [
        {"metric": "summary.early_exit", "equals": False},
        {"metric": "summary.windows", "min": 10},
        {"metric": "stitched_oos_metrics.profit_factor", "min": 1.2},
        {"metric": "stitched_oos_metrics.mar", "min": 0.4},
        {"metric": "stitched_oos_metrics.total_trades", "min": 500},
        {"metric": "stitched_oos_metrics.apex_rule_violations", "max": 0},
    ],
    "wfa_oos_monkey_test": [
        {"metric": "summary.core_beats_monkey_net_profit_rate", "min": 0.80},
        {"metric": "summary.core_beats_monkey_max_drawdown_rate", "min": 0.80},
        {"metric": "summary.core_metrics.apex_rule_violations", "max": 0},
    ],
    "wfa_oos_monte_carlo": [
        {"metric": "summary.probability_profit_before_drawdown", "exclusive_min": 0.50},
    ],
    "simulated_incubation_core": [
        {"metric": "metrics.profit_factor", "min": 1.0},
        {"metric": "metrics.mar", "min": 1.0},
        {"metric": "metrics.total_trades", "min": 75},
        {"metric": "metrics.apex_rule_violations", "max": 0},
    ],
    "simulated_incubation_monkey": [
        {"metric": "summary.core_beats_monkey_net_profit_rate", "min": 0.80},
        {"metric": "summary.core_beats_monkey_max_drawdown_rate", "min": 0.80},
        {"metric": "summary.core_metrics.apex_rule_violations", "max": 0},
    ],
    ACCEPTANCE_STAGE: [
        {"metric": "metrics.profit_factor", "min": 1.0},
        {"metric": "metrics.mar", "min": 1.0},
        {"metric": "metrics.total_trades", "min": 25},
        {"metric": "metrics.apex_rule_violations", "max": 0},
    ],
}

DEFAULT_SHORTLIST_DATA_WINDOW = {
    "mode": "random_months",
    "months": 18,
    "seed": 31,
    "avoid_ranges": [{"start_date": "2020-02-01", "end_date": "2021-06-30"}],
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


def canonicalize_campaign_config(cfg: dict, *, include_acceptance: bool = True) -> dict:
    out = copy.deepcopy(cfg)
    campaign_tests = copy.deepcopy(out.get("campaign_tests") or {})
    stage_order = DEFAULT_STAGE_ORDER if include_acceptance else PRE_ACCEPTANCE_STAGE_ORDER
    campaign_tests["stage_order"] = list(stage_order)
    for stage_name in DEFAULT_STAGE_ORDER:
        stage_cfg = copy.deepcopy(campaign_tests.get(stage_name) or {})
        stage_cfg.pop("enabled", None)
        stage_cfg["criteria"] = copy.deepcopy(DEFAULT_STAGE_CRITERIA[stage_name])
        if stage_name in {"limited_core_grid_test", "limited_monkey_test"}:
            stage_cfg.pop("data_subset", None)
            stage_cfg["data_window"] = copy.deepcopy(DEFAULT_SHORTLIST_DATA_WINDOW)
        if stage_name == ACCEPTANCE_STAGE:
            stage_cfg.setdefault("train_months", 24)
            stage_cfg.setdefault("test_months", 6)
            if not include_acceptance:
                stage_cfg["enabled"] = False
        campaign_tests[stage_name] = stage_cfg
    out["campaign_tests"] = campaign_tests
    return out


def apply_fast_runtime_defaults(cfg: dict, workers: int | None = None) -> dict:
    out = copy.deepcopy(cfg)
    worker_count = max(1, int(workers or min(6, os.cpu_count() or 1)))
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
    cfg = canonicalize_campaign_config(load_yaml(config_path), include_acceptance=include_acceptance)
    if fast_runtime_defaults:
        cfg = apply_fast_runtime_defaults(cfg)
    root = Path(out_dir) if out_dir else variant_root(cfg) / "campaign_tests"
    root.mkdir(parents=True, exist_ok=True)
    _write_config_snapshot(root / "config_snapshot.yaml", cfg)

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
        write_json(stage_dir / "stage_result.json", result)
        if not result["passed"] and not continue_on_failure:
            halted = True

    summary = {
        "campaign_id": cfg.get("campaign_id"),
        "variant_id": cfg.get("variant_id"),
        "symbol": cfg.get("symbol") or (cfg.get("data") or {}).get("symbol"),
        "dataset_id": cfg.get("dataset_id") or (cfg.get("data") or {}).get("dataset_id"),
        "timeframe": config_timeframe(cfg),
        "config_path": str(config_path),
        "output_dir": str(root),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "skip_validation": skip_validation,
        "fast_runtime_defaults": fast_runtime_defaults,
        "passed": all(result["passed"] or result["status"] == "skipped" for result in results)
        and any(result["status"] == "passed" for result in results),
        "halted": halted,
        "stages": results,
    }
    write_json(root / "campaign_test_summary.json", summary)
    (root / "campaign_test_summary.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


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
        if k not in {"trades", "market", "detail", "core_grid_results"}
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
    market, detail, quality, input_hash = _prepare_stage_data_cached(
        cfg,
        subset,
        stage_dir,
        skip_validation,
        data_cache=context.get("_prepared_data_cache"),
    )
    report_dir = stage_dir if grid_cfg.get("retain_iteration_reports", True) else None
    results, summary = run_core_grid(
        market,
        cfg,
        grid_cfg,
        cfg.get("benchmarks", {}),
        report_dir=report_dir,
        detail_data=detail,
    )
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
    report_dir = stage_dir if monkey_cfg.get("retain_iteration_reports", True) else None
    results, summary = run_monkey(
        market,
        test_cfg,
        monkey_cfg,
        test_cfg.get("benchmarks", {}),
        report_dir=report_dir,
        detail_data=detail,
    )
    summary["selected_core_params"] = selected_params
    summary["selected_core_row"] = selected_row.to_dict() if selected_row is not None else {}
    report_timezone = market_timezone(cfg)
    write_report_csv(results, stage_dir / "monkey_results.csv", report_timezone, index=False)
    write_json(stage_dir / "monkey_summary.json", summary)
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
        {"data_window": {"mode": "exclude_last_months", "months": 18}, **stage_cfg},
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
    summary.update(
        write_equity_report(
            trades,
            stage_dir,
            initial_balance=initial_balance,
            timezone=report_timezone,
            title=f"{cfg.get('campaign_id')} / {cfg.get('variant_id')} staged WFA OOS equity curve",
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
    report_timezone = market_timezone(cfg)
    write_report_csv(results, stage_dir / "wfa_oos_monkey_results.csv", report_timezone, index=False)
    write_json(stage_dir / "wfa_oos_monkey_summary.json", summary)
    return {"summary": summary, "artifacts": _stage_artifacts(stage_dir)}


def _run_wfa_oos_monte_carlo(cfg: dict, stage_cfg: dict, stage_dir: Path, context: dict) -> dict:
    trades = _required_context_frame(context, "wfa_trades", "WFA OOS Monte Carlo requires walk_forward_analysis trades.")
    mc_cfg = {**cfg.get("benchmarks", {}), **copy.deepcopy(cfg.get("monte_carlo", {})), **stage_cfg}
    mc_cfg["_core"] = cfg.get("core", {})
    rules = PropRules.from_dict(cfg.get("prop_rules", {}))
    retain_path_trades = bool(mc_cfg.get("retain_path_trades", False))
    retain_path_events = bool(mc_cfg.get("retain_path_events", False))
    if retain_path_trades or retain_path_events:
        results, summary, path_trades, path_events = run_monte_carlo_with_audit(trades, mc_cfg, rules)
    else:
        results, summary = run_monte_carlo(trades, mc_cfg, rules)
        path_trades = pd.DataFrame()
        path_events = pd.DataFrame()
    report_timezone = market_timezone(cfg)
    write_report_csv(results, stage_dir / "wfa_oos_monte_carlo_results.csv", report_timezone, index=False)
    if retain_path_trades:
        write_report_csv(path_trades, stage_dir / "wfa_oos_monte_carlo_path_trades.csv", report_timezone, index=False)
    if retain_path_events:
        write_report_csv(path_events, stage_dir / "wfa_oos_monte_carlo_path_events.csv", report_timezone, index=False)
    write_json(stage_dir / "wfa_oos_monte_carlo_summary.json", summary)
    return {"summary": summary, "artifacts": _stage_artifacts(stage_dir)}


def _run_incubation_core(
    cfg: dict,
    stage_cfg: dict,
    stage_dir: Path,
    skip_validation: bool,
    context: dict,
) -> dict:
    train_selection_payload = {}
    if (stage_cfg.get("train_selection") or {}).get("enabled", False):
        selected_params, train_selection_payload = _run_incubation_train_selection(
            cfg,
            stage_cfg["train_selection"],
            stage_dir / "train_selection",
            skip_validation,
            context.get("_prepared_data_cache"),
        )
    else:
        selected_params = stage_cfg.get("selected_params") or context.get("incubation_params") or {}
    test_cfg = apply_dotted_params(cfg, selected_params) if selected_params else copy.deepcopy(cfg)
    subset = _stage_subset(
        test_cfg,
        {"data_window": {"mode": "last_months", "months": 18}, **stage_cfg},
        "core",
    )
    market, detail, quality, input_hash = _prepare_stage_data_cached(
        test_cfg,
        subset,
        stage_dir,
        skip_validation,
        data_cache=context.get("_prepared_data_cache"),
    )
    result = BacktestEngine(test_cfg).run(market, detail_data=detail)
    trades = result["trades"]
    report_timezone = market_timezone(test_cfg)
    write_report_csv(trades, stage_dir / "trade_log.csv", report_timezone, index=False)
    write_report_csv(result["daily"], stage_dir / "daily_results.csv", report_timezone, index=False)
    metrics = {**result["metrics"], "diagnostics": result.get("diagnostics", {})}
    write_json(stage_dir / "metrics.json", metrics)
    write_equity_report(
        trades,
        stage_dir,
        initial_balance=float(test_cfg.get("core", {}).get("initial_balance", 0.0)),
        timezone=report_timezone,
        title=f"{test_cfg.get('campaign_id')} / {test_cfg.get('variant_id')} incubation equity curve",
    )
    return {
        "metrics": result["metrics"],
        "diagnostics": result.get("diagnostics", {}),
        "selected_params": selected_params,
        "incubation_train_selection": train_selection_payload,
        "data_quality": quality,
        "input_hash": input_hash,
        "artifacts": _stage_artifacts(stage_dir),
        "trades": trades,
        "market": market,
        "detail": detail,
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

    parameters = (
        stage_cfg.get("parameters")
        or (cfg.get("wfa") or {}).get("parameters")
        or (cfg.get("core_grid") or {}).get("parameters")
        or {}
    )
    if not parameters:
        raise ValueError("acceptance_oos_test requires a parameter grid.")

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
    result = BacktestEngine(test_cfg).run(test, detail_data=test_detail)
    trades = result["trades"]
    report_timezone = market_timezone(test_cfg)
    write_report_csv(trades, stage_dir / "trade_log.csv", report_timezone, index=False)
    write_report_csv(result["daily"], stage_dir / "daily_results.csv", report_timezone, index=False)
    metrics = {**result["metrics"], "diagnostics": result.get("diagnostics", {})}
    write_json(stage_dir / "metrics.json", metrics)
    acceptance_summary = _acceptance_summary(window, train, test, selected_params, train_selection_payload, result)
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
    report_timezone = market_timezone(cfg)
    write_report_csv(results, stage_dir / "incubation_monkey_results.csv", report_timezone, index=False)
    write_json(stage_dir / "incubation_monkey_summary.json", summary)
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
        out.append(
            {
                "metric": metric,
                "actual": actual,
                "expected": expected,
                "passed": bool(passed),
            }
        )
    return out


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


def _acceptance_base_subset(cfg: dict, stage_cfg: dict) -> dict:
    if stage_cfg.get("data_subset"):
        return dict(stage_cfg["data_subset"])
    return dict((cfg.get("core") or {}).get("data_subset") or (cfg.get("data") or {}).get("data_subset") or {})


def _planned_acceptance_subset(
    base_subset: dict,
    train_months: int,
    test_months: int,
) -> tuple[dict | None, dict | None]:
    end = _subset_end_date(base_subset)
    if end is None:
        return (dict(base_subset) if base_subset else None), None
    window = _acceptance_window_from_end(end, train_months, test_months)
    start = _subset_start_date(base_subset)
    if start is not None and start > window["train_start"]:
        raise ValueError(
            "acceptance_oos_test requires the configured data range to cover the full "
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
) -> dict:
    if planned_window is not None:
        return planned_window
    if market.empty or "session_date" not in market.columns:
        raise ValueError("acceptance_oos_test cannot infer latest data date from an empty market slice.")
    sessions = pd.to_datetime(market["session_date"], errors="coerce").dropna()
    if sessions.empty:
        raise ValueError("acceptance_oos_test cannot infer latest data date from session_date.")
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
    fallback = dict((cfg.get(fallback_section) or {}).get("data_subset") or (cfg.get("data") or {}).get("data_subset") or {})
    window = stage_cfg.get("data_window")
    if window:
        return _subset_from_window(fallback, window)
    return fallback or None


def _subset_from_window(base_subset: dict, window: dict) -> dict:
    if not base_subset.get("end_date") and not base_subset.get("start_date"):
        return base_subset
    mode = str(window.get("mode", "")).lower()
    months = int(window.get("months", 18))
    start = pd.Timestamp(base_subset.get("start_date")) if base_subset.get("start_date") else None
    end = pd.Timestamp(base_subset.get("end_date")) if base_subset.get("end_date") else None
    out = dict(base_subset)
    if mode == "exclude_last_months" and end is not None:
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
    return out


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
    parameters = (
        selection_cfg.get("parameters")
        or (cfg.get("wfa") or {}).get("parameters")
        or (cfg.get("core_grid") or {}).get("parameters")
        or {}
    )
    if not parameters:
        raise ValueError("incubation train selection requires a parameter grid.")
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
    selected_params = _core_grid_params_from_row(selected_row, parameters)
    report_timezone = market_timezone(cfg)
    write_report_csv(results, train_dir / f"{result_prefix}_train_grid_results.csv", report_timezone, index=False)
    summary["selected_params"] = selected_params
    summary["selected_row"] = selected_row.to_dict() if selected_row is not None else {}
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


def _select_core_grid_params(results: pd.DataFrame, parameters: dict, selection_cfg: dict) -> dict:
    return _core_grid_params_from_row(_select_core_grid_row(results, parameters, selection_cfg), parameters)


def _select_core_grid_row(results: pd.DataFrame, parameters: dict, selection_cfg: dict):
    if results.empty:
        return None
    candidates = results.copy()
    min_total_trades = selection_cfg.get("selection_min_total_trades")
    if min_total_trades is not None and "total_trades" in candidates.columns:
        filtered = candidates[pd.to_numeric(candidates["total_trades"], errors="coerce") >= float(min_total_trades)]
        if not filtered.empty:
            candidates = filtered
    min_trades_per_year = selection_cfg.get("selection_min_trades_per_year")
    if min_trades_per_year is not None and "trades_per_year" in candidates.columns:
        filtered = candidates[pd.to_numeric(candidates["trades_per_year"], errors="coerce") >= float(min_trades_per_year)]
        if not filtered.empty:
            candidates = filtered
    exclusive_min_trades_per_year = selection_cfg.get("selection_exclusive_min_trades_per_year")
    if exclusive_min_trades_per_year is not None and "trades_per_year" in candidates.columns:
        filtered = candidates[
            pd.to_numeric(candidates["trades_per_year"], errors="coerce")
            > float(exclusive_min_trades_per_year)
        ]
        if not filtered.empty:
            candidates = filtered
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
    return {
        "stage": stage_name,
        "label": STAGE_LABELS.get(stage_name, stage_name),
        "status": "error",
        "passed": False,
        "error": str(exc),
        "criteria": [],
    }


def _markdown_summary(summary: dict) -> str:
    lines = [
        f"# Campaign Test Summary",
        "",
        f"- Campaign: `{summary.get('campaign_id')}`",
        f"- Variant: `{summary.get('variant_id')}`",
        f"- Timeframe: `{summary.get('timeframe')}`",
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
