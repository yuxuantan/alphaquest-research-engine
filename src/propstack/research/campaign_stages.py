from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path
import shutil
from typing import Any

import pandas as pd

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
from propstack.utils.params import apply_dotted_params
from propstack.utils.reports import market_timezone, write_report_csv


DEFAULT_STAGE_ORDER = [
    "limited_core_grid_test",
    "limited_monkey_test",
    "walk_forward_analysis",
    "wfa_oos_monkey_test",
    "wfa_oos_monte_carlo",
    "simulated_incubation_core",
    "simulated_incubation_monkey",
]

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
        {"metric": "stitched_oos_metrics.profit_factor", "min": 1.5},
        {"metric": "stitched_oos_metrics.mar", "min": 1.5},
        {"metric": "stitched_oos_metrics.expectancy_r", "min": 0.2},
        {"metric": "stitched_oos_metrics.total_trades", "min": 500},
        {"metric": "stitched_oos_metrics.win_rate", "min": 0.45},
        {"metric": "stitched_oos_metrics.apex_rule_violations", "max": 0},
    ],
    "wfa_oos_monkey_test": [
        {"metric": "summary.core_beats_monkey_net_profit_rate", "min": 0.90},
        {"metric": "summary.core_beats_monkey_max_drawdown_rate", "min": 0.90},
        {"metric": "summary.core_metrics.apex_rule_violations", "max": 0},
    ],
    "wfa_oos_monte_carlo": [
        {"metric": "summary.probability_profit_before_drawdown", "min": 0.50},
    ],
    "simulated_incubation_core": [
        {"metric": "metrics.profit_factor", "min": 1.2},
        {"metric": "metrics.mar", "min": 1.2},
        {"metric": "metrics.expectancy_r", "min": 0.15},
        {"metric": "metrics.total_trades", "min": 75},
        {"metric": "metrics.win_rate", "min": 0.40},
        {"metric": "metrics.apex_rule_violations", "max": 0},
    ],
    "simulated_incubation_monkey": [
        {"metric": "summary.core_beats_monkey_net_profit_rate", "min": 0.80},
        {"metric": "summary.core_beats_monkey_max_drawdown_rate", "min": 0.80},
        {"metric": "summary.core_metrics.apex_rule_violations", "max": 0},
    ],
}

STAGE_LABELS = {
    "limited_core_grid_test": "Limited Core Grid Test",
    "limited_monkey_test": "Limited Monkey Test",
    "walk_forward_analysis": "Walk Forward Analysis (WFA)",
    "wfa_oos_monkey_test": "WFA OOS Monkey Test",
    "wfa_oos_monte_carlo": "WFA OOS Monte Carlo",
    "simulated_incubation_core": "Simulated Incubation (OOS) Core",
    "simulated_incubation_monkey": "Simulated Incubation (OOS) Monkey",
}


def run_campaign_stage_tests(
    config_path: str | Path,
    *,
    skip_validation: bool = True,
    continue_on_failure: bool = False,
    out_dir: str | Path | None = None,
) -> dict:
    config_path = Path(config_path)
    cfg = load_yaml(config_path)
    root = Path(out_dir) if out_dir else variant_root(cfg) / "campaign_tests"
    root.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        shutil.copy2(config_path, root / "config_snapshot.yaml")

    campaign_tests = cfg.get("campaign_tests") or {}
    stage_order = list(campaign_tests.get("stage_order", DEFAULT_STAGE_ORDER))
    context: dict[str, Any] = {}
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
        payload = _run_limited_core_grid(cfg, stage_cfg, stage_dir, skip_validation)
    elif stage_name == "limited_monkey_test":
        payload = _run_limited_monkey(cfg, stage_cfg, stage_dir, skip_validation)
    elif stage_name == "walk_forward_analysis":
        payload = _run_wfa_stage(cfg, stage_cfg, stage_dir, skip_validation)
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
    else:
        raise ValueError(f"Unsupported campaign test stage: {stage_name}")

    criteria = _criteria_for_stage(stage_name, stage_cfg)
    criteria_results = evaluate_criteria(payload, criteria)
    passed = all(item["passed"] for item in criteria_results)
    completed = datetime.now()
    public_payload = {k: v for k, v in payload.items() if k not in {"trades", "market", "detail"}}
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


def _run_limited_core_grid(cfg: dict, stage_cfg: dict, stage_dir: Path, skip_validation: bool) -> dict:
    grid_cfg = _merged_section(cfg, "core_grid", stage_cfg)
    subset = _stage_subset(cfg, stage_cfg, "core_grid")
    market, detail, quality, input_hash = _prepare_stage_data(cfg, subset, stage_dir, skip_validation)
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
    }


def _run_limited_monkey(cfg: dict, stage_cfg: dict, stage_dir: Path, skip_validation: bool) -> dict:
    monkey_cfg = _merged_section(cfg, "monkey", stage_cfg)
    subset = _stage_subset(cfg, stage_cfg, "monkey")
    market, detail, quality, input_hash = _prepare_stage_data(cfg, subset, stage_dir, skip_validation)
    report_dir = stage_dir if monkey_cfg.get("retain_iteration_reports", True) else None
    results, summary = run_monkey(
        market,
        cfg,
        monkey_cfg,
        cfg.get("benchmarks", {}),
        report_dir=report_dir,
        detail_data=detail,
    )
    report_timezone = market_timezone(cfg)
    write_report_csv(results, stage_dir / "monkey_results.csv", report_timezone, index=False)
    write_json(stage_dir / "monkey_summary.json", summary)
    return {
        "summary": summary,
        "data_quality": quality,
        "input_hash": input_hash,
        "artifacts": _stage_artifacts(stage_dir),
        "market": market,
        "detail": detail,
    }


def _run_wfa_stage(cfg: dict, stage_cfg: dict, stage_dir: Path, skip_validation: bool) -> dict:
    wfa_cfg = _merged_section(cfg, "wfa", stage_cfg)
    wfa_cfg.setdefault("mode", "unanchored")
    wfa_cfg.setdefault("train_months", 48)
    wfa_cfg.setdefault("test_months", 12)
    wfa_cfg.setdefault("step_months", 12)
    wfa_cfg.setdefault("objective", "profit_factor")
    wfa_cfg.setdefault("selection_min_trades_per_year", 52)
    wfa_cfg.setdefault("early_exit_min_train_profit_factor", 1.0)
    subset = _stage_subset(
        cfg,
        {"data_window": {"mode": "exclude_last_months", "months": 18}, **stage_cfg},
        "wfa",
    )
    market, detail, quality, input_hash = _prepare_stage_data(cfg, subset, stage_dir, skip_validation, show_progress=True)
    results, summary, trades = run_wfa(
        market,
        cfg,
        wfa_cfg,
        cfg.get("benchmarks", {}),
        include_trade_log=True,
        train_grid_dir=stage_dir,
        detail_data=detail,
    )
    report_timezone = market_timezone(cfg)
    write_report_csv(results, stage_dir / "wfa_results.csv", report_timezone, index=False)
    write_report_csv(trades, stage_dir / "wfa_oos_trade_log.csv", report_timezone, index=False)
    initial_balance = float(cfg.get("core", {}).get("initial_balance", 0.0))
    stitched_metrics = calculate_metrics(trades, initial_balance=initial_balance)
    summary["stitched_oos_metrics"] = stitched_metrics
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
    monkey_cfg.setdefault("beat_threshold", 0.90)
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
    selected_params = stage_cfg.get("selected_params") or context.get("incubation_params") or {}
    test_cfg = apply_dotted_params(cfg, selected_params) if selected_params else copy.deepcopy(cfg)
    subset = _stage_subset(
        test_cfg,
        {"data_window": {"mode": "last_months", "months": 18}, **stage_cfg},
        "core",
    )
    market, detail, quality, input_hash = _prepare_stage_data(test_cfg, subset, stage_dir, skip_validation)
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
        "data_quality": quality,
        "input_hash": input_hash,
        "artifacts": _stage_artifacts(stage_dir),
        "trades": trades,
        "market": market,
        "detail": detail,
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


def _prepare_stage_data(
    cfg: dict,
    subset: dict | None,
    stage_dir: Path,
    skip_validation: bool,
    show_progress: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame | None, dict, str]:
    timeframe = config_timeframe(cfg)
    output_dir = None if skip_validation else stage_dir / "validation"
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
    return market, detail, quality, input_hash


def evaluate_criteria(payload: dict, criteria: list[dict]) -> list[dict]:
    out = []
    for item in criteria:
        metric = item["metric"]
        actual = _lookup(payload, metric)
        passed = True
        expected = {}
        if "min" in item:
            expected["min"] = item["min"]
            passed = passed and _numeric(actual) >= float(item["min"])
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


def _criteria_for_stage(stage_name: str, stage_cfg: dict) -> list[dict]:
    configured = stage_cfg.get("criteria")
    if configured:
        if isinstance(configured, dict):
            return [{"metric": metric, **rule} for metric, rule in configured.items()]
        return list(configured)
    return copy.deepcopy(DEFAULT_STAGE_CRITERIA.get(stage_name, []))


def _stage_config(campaign_tests: dict, stage_name: str) -> dict:
    return copy.deepcopy(campaign_tests.get(stage_name) or {})


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
