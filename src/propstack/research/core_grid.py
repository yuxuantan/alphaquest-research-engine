from __future__ import annotations

from itertools import product
from pathlib import Path

import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.backtest.metrics import benchmark
from propstack.utils.params import apply_dotted_params
from propstack.utils.progress import progress_bar
from propstack.utils.reports import market_timezone, write_report_csv


def parameter_combinations(params: dict, label: str = "core_grid.parameters") -> list[dict]:
    _validate_parameter_grid(params, label)
    keys = list(params.keys())
    return [dict(zip(keys, values)) for values in product(*(params[k] for k in keys))]


def run_core_grid(
    data: pd.DataFrame,
    base_config: dict,
    grid_config: dict,
    benchmarks: dict,
    report_dir: str | Path | None = None,
    parameter_label: str = "core_grid.parameters",
) -> tuple[pd.DataFrame, dict]:
    rows = []
    parameters = grid_config.get("parameters", {})
    combos = parameter_combinations(parameters, parameter_label)
    report_paths = _prepare_iteration_report_paths(report_dir)
    report_timezone = market_timezone(base_config)
    progress = progress_bar(len(combos), "core grid")
    for idx, combo in enumerate(combos, start=1):
        cfg = apply_dotted_params(base_config, combo)
        result = BacktestEngine(cfg).run(data)
        metrics = result["metrics"]
        passed, reason = benchmark(metrics, benchmarks)
        rows.append(
            {
                "run_id": idx,
                **combo,
                "total_trades": metrics["total_trades"],
                "trades_per_year": metrics["trades_per_year"],
                "net_profit": metrics["net_profit"],
                "profit_factor": metrics["profit_factor"],
                "expectancy_r": metrics["expectancy_r"],
                "max_drawdown": metrics["max_drawdown"],
                "max_drawdown_pct": metrics["max_drawdown_pct"],
                "cagr": metrics["cagr"],
                "mar": metrics["mar"],
                "win_rate": metrics["win_rate"],
                "profitable": metrics["net_profit"] > 0,
                "worst_day": metrics["worst_day"],
                "best_day_concentration": metrics["best_day_concentration"],
                "consecutive_losses": metrics["max_consecutive_losses"],
                "benchmark_passed": passed,
                "failure_reason": reason,
            }
        )
        _append_iteration_report(report_paths, "trades", result["trades"], idx, combo, report_timezone)
        _append_iteration_report(report_paths, "daily", result["daily"], idx, combo, report_timezone)
        progress.update(idx)
    df = pd.DataFrame(rows)
    passing = int(df["benchmark_passed"].sum()) if len(df) else 0
    profitable = int(df["profitable"].sum()) if len(df) else 0
    profitable_rate = float(profitable / len(df)) if len(df) else 0.0
    profitable_threshold = _profitable_iteration_threshold(grid_config, benchmarks)
    top = df.sort_values(["benchmark_passed", "net_profit"], ascending=[False, False]).head(10)
    summary = {
        "parameter_value_counts": {key: len(values) for key, values in parameters.items()},
        "expected_combinations": _expected_combination_count(parameters),
        "total_combinations_tested": int(len(df)),
        "number_passing_benchmark": passing,
        "percentage_passing_benchmark": float(passing / len(df)) if len(df) else 0.0,
        "profitable_iterations": profitable,
        "percentage_profitable_iterations": profitable_rate,
        "profitable_iteration_threshold": profitable_threshold,
        "meets_profitable_iteration_threshold": profitable_rate >= profitable_threshold,
        "top_10_combinations": top.to_dict(orient="records"),
        "stable_parameter_zones": summarize_stability(df),
        "iteration_reports_retained": report_paths is not None,
        "iteration_report_files": _iteration_report_files(report_paths),
        "data_subset": grid_config.get("data_subset", {}),
    }
    return df, summary


def summarize_stability(df: pd.DataFrame) -> dict:
    if df.empty or "benchmark_passed" not in df:
        return {}
    zones = {}
    for col in [
        "entry.params.reclaim_window_bars",
        "entry.params.max_opening_range_pct_of_open",
        "entry.params.confirmation_minutes",
        "tp.params.target_r_multiple",
        "tp.params.extension_fraction",
        "sl.params.stop_offset_ticks",
        "sl.params.max_stop_points",
        "entry.params.max_trades_per_day",
    ]:
        if col in df.columns:
            grouped = df.groupby(col)["benchmark_passed"].mean().sort_values(ascending=False)
            zones[col] = grouped.to_dict()
    return zones


def _validate_parameter_grid(params: dict, label: str) -> None:
    if not isinstance(params, dict):
        raise ValueError(f"{label} must be a mapping of dotted parameter paths to value lists.")
    for key, values in params.items():
        if not isinstance(values, list):
            raise ValueError(f"{label}.{key} must be a list of values.")
        if not values:
            raise ValueError(f"{label}.{key} must define at least one value.")


def _expected_combination_count(params: dict) -> int:
    total = 1
    for values in params.values():
        total *= len(values)
    return total


def _profitable_iteration_threshold(grid_config: dict, benchmarks: dict) -> float:
    return float(
        grid_config.get(
            "min_profitable_iteration_rate",
            benchmarks.get("min_core_grid_profitable_iteration_rate", 0.70),
        )
    )


def _prepare_iteration_report_paths(report_dir: str | Path | None) -> dict[str, Path] | None:
    if report_dir is None:
        return None
    root = Path(report_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "trades": root / "core_grid_iteration_trades.csv",
        "daily": root / "core_grid_iteration_daily.csv",
    }
    for path in paths.values():
        if path.exists():
            path.unlink()
    return paths


def _append_iteration_report(
    paths: dict[str, Path] | None,
    name: str,
    frame: pd.DataFrame,
    run_id: int,
    combo: dict,
    timezone: str | None = None,
) -> None:
    if paths is None or frame.empty:
        return
    out = frame.copy()
    out.insert(0, "run_id", run_id)
    for offset, (key, value) in enumerate(combo.items(), start=1):
        out.insert(offset, key, value)
    path = paths[name]
    write_report_csv(out, path, timezone, mode="a", header=not path.exists(), index=False)


def _iteration_report_files(paths: dict[str, Path] | None) -> list[str]:
    if paths is None:
        return []
    return [str(path) for path in paths.values()]
