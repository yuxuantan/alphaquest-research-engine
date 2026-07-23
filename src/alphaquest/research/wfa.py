from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
import math
import os
from pathlib import Path
import time

import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.backtest.metrics import benchmark
from alphaquest.research.core_grid import _evaluate_core_grid_combo, parameter_combinations, run_core_grid
from alphaquest.research.execution import run_research_backtest
from alphaquest.utils.hashing import object_sha256
from alphaquest.utils.params import apply_dotted_params
from alphaquest.utils.progress import progress_bar
from alphaquest.utils.reports import market_timezone, write_report_csv

_WFA_OBJECTIVES = {
    "net_profit": "net_profit",
    "net profit": "net_profit",
    "net-profit": "net_profit",
    "mar": "mar",
    "profit_factor": "profit_factor",
    "profit factor": "profit_factor",
    "profit-factor": "profit_factor",
    "pf": "profit_factor",
}

_OBJECTIVE_LABELS = {
    "net_profit": "net_profit",
    "mar": "MAR",
    "profit_factor": "Profit Factor",
}

_WFA_WORKER_DATA = None
_WFA_WORKER_DETAIL_DATA = None
_WFA_WORKER_BASE_CONFIG = None
_WFA_WORKER_BENCHMARKS = None
_WFA_WORKER_SLICE_CACHE = None


class NoEligibleWfaSelectionError(ValueError):
    """Raised when the WFA in-sample grid has no row eligible for selection."""


def create_windows(
    data: pd.DataFrame,
    train_months: int,
    test_months: int,
    step_months: int | None = None,
    mode: str = "unanchored",
):
    start = pd.Timestamp(data["timestamp"].min()).tz_localize(None).normalize()
    end = pd.Timestamp(data["timestamp"].max()).tz_localize(None).normalize()
    step_months = test_months if step_months is None else step_months
    mode = str(mode).lower()
    _validate_window_config(train_months, test_months, step_months, mode)

    if mode == "anchored":
        test_start = start + pd.DateOffset(months=train_months)
        while True:
            test_end = test_start + pd.DateOffset(months=test_months)
            if test_start > end:
                break
            yield start, test_start, test_start, test_end
            test_start = test_start + pd.DateOffset(months=step_months)
        return

    train_start = start
    while True:
        train_end = train_start + pd.DateOffset(months=train_months)
        test_start = train_end
        test_end = test_start + pd.DateOffset(months=test_months)
        if test_start > end:
            break
        yield train_start, train_end, test_start, test_end
        train_start = train_start + pd.DateOffset(months=step_months)


def _slice(data: pd.DataFrame, start, end):
    naive = data["timestamp"].dt.tz_localize(None)
    return data[(naive >= start) & (naive < end)].copy()


def run_wfa(
    data: pd.DataFrame,
    base_config: dict,
    wfa_config: dict,
    benchmarks: dict,
    include_trade_log: bool = False,
    train_grid_dir: str | Path | None = None,
    detail_data: pd.DataFrame | None = None,
    input_hash: str | None = None,
):
    rows = []
    trade_frames = []
    train_grid_paths = []
    reused_train_grid_count = 0
    window_timings = []
    phase_timings: dict[str, float] = {}
    grid_config = _wfa_grid_config(wfa_config)
    objective = grid_config["objective"]
    selection_filter = grid_config["selection_filter"]
    reuse_existing_train_grids = bool(wfa_config.get("reuse_existing_train_grids", False))
    strict_train_grid_reuse = bool(wfa_config.get("strict_train_grid_reuse", True))
    train_grid_metadata = _train_grid_metadata(base_config, grid_config, input_hash)
    early_exit_min_profit_factor = wfa_config.get("early_exit_min_train_profit_factor")
    early_exit_require_train_profitable = bool(wfa_config.get("early_exit_require_train_profitable", False))
    windows = list(
        create_windows(
            data,
            int(wfa_config.get("train_months", 3)),
            int(wfa_config.get("test_months", 1)),
            int(wfa_config["step_months"]) if "step_months" in wfa_config else None,
            _wfa_mode(wfa_config),
        )
    )
    if train_grid_dir is not None:
        if not reuse_existing_train_grids:
            _clear_window_train_grid_reports(train_grid_dir)
    progress = progress_bar(len(windows), "walk-forward windows", show_timing=True)
    progress.update(0, force=True)
    use_pooled_grid = _use_pooled_wfa_grid(grid_config)
    pooled_combos = parameter_combinations(grid_config.get("parameters", {}), "wfa.parameters") if use_pooled_grid else None
    pooled_executor = (
        _start_wfa_grid_pool(data, detail_data, base_config, benchmarks, grid_config) if use_pooled_grid else None
    )
    try:
        for wid, (tr_s, tr_e, te_s, te_e) in enumerate(windows, start=1):
            window_started = time.perf_counter()
            slice_started = time.perf_counter()
            train = _slice(data, tr_s, tr_e)
            test = _slice(data, te_s, te_e)
            train_detail = _slice(detail_data, tr_s, tr_e) if detail_data is not None and pooled_executor is None else None
            test_detail = _slice(detail_data, te_s, te_e) if detail_data is not None else None
            slice_seconds = _elapsed(slice_started)
            _add_timing(phase_timings, "slice_windows", slice_seconds)
            _log_window_start(wid, len(windows), tr_s, tr_e, te_s, te_e, len(train), len(test))
            if train.empty or test.empty:
                _log_window_skip(wid, len(windows), "empty train/test slice")
                progress.update(wid, force=True)
                window_timings.append(
                    {
                        "window_id": wid,
                        "slice_seconds": slice_seconds,
                        "total_seconds": _elapsed(window_started),
                        "skipped": True,
                    }
                )
                continue
            train_grid_path = _existing_window_train_grid(train_grid_dir, wid)
            reused_train_grid = reuse_existing_train_grids and train_grid_path is not None
            train_grid_started = time.perf_counter()
            if reused_train_grid:
                grid_df = _read_reusable_window_train_grid(
                    train_grid_path,
                    wid,
                    tr_s,
                    tr_e,
                    te_s,
                    te_e,
                    objective,
                    grid_config,
                    train_grid_metadata,
                    strict=strict_train_grid_reuse,
                )
                if grid_df is None:
                    reused_train_grid = False
                else:
                    print(f"walk-forward {wid}/{len(windows)} reused train grid {train_grid_path}", flush=True)
            if not reused_train_grid:
                if pooled_executor is not None and pooled_combos is not None:
                    grid_df = _run_pooled_window_train_grid(
                        pooled_executor,
                        wid,
                        len(windows),
                        tr_s,
                        tr_e,
                        pooled_combos,
                        _pooled_wfa_workers(grid_config),
                    )
                else:
                    grid_df, _ = run_core_grid(
                        train,
                        base_config,
                        grid_config,
                        benchmarks,
                        parameter_label="wfa.parameters",
                        detail_data=train_detail,
                    )
            train_grid_seconds = _elapsed(train_grid_started)
            _add_timing(
                phase_timings,
                "train_grid_reuse" if reused_train_grid else "train_grid_compute",
                train_grid_seconds,
            )
            if grid_df.empty:
                _log_window_skip(wid, len(windows), "no in-sample grid results")
                progress.update(wid, force=True)
                window_timings.append(
                    {
                        "window_id": wid,
                        "slice_seconds": slice_seconds,
                        "train_grid_seconds": train_grid_seconds,
                        "total_seconds": _elapsed(window_started),
                        "skipped": True,
                    }
                )
                continue
            try:
                best = _select_best_in_sample(grid_df, objective, selection_filter)
            except NoEligibleWfaSelectionError as exc:
                _log_window_skip(wid, len(windows), f"early exit: {exc}")
                rows.append(
                    _early_exit_row(
                        wid,
                        tr_s,
                        tr_e,
                        te_s,
                        te_e,
                        objective,
                        {},
                        "no_in_sample_rows_after_selection_filter",
                    )
                )
                progress.update(wid, force=True)
                window_timings.append(
                    {
                        "window_id": wid,
                        "slice_seconds": slice_seconds,
                        "train_grid_seconds": train_grid_seconds,
                        "total_seconds": _elapsed(window_started),
                        "early_exit": True,
                    }
                )
                break
            if early_exit_require_train_profitable and _metric_value(best, "net_profit") <= 0.0:
                _log_window_skip(
                    wid,
                    len(windows),
                    f"early exit: selected in-sample net_profit {_metric_value(best, 'net_profit'):.2f} "
                    "<= 0.00",
                )
                rows.append(_early_exit_row(wid, tr_s, tr_e, te_s, te_e, objective, best, "selected_train_net_profit_not_positive"))
                progress.update(wid, force=True)
                window_timings.append(
                    {
                        "window_id": wid,
                        "slice_seconds": slice_seconds,
                        "train_grid_seconds": train_grid_seconds,
                        "total_seconds": _elapsed(window_started),
                        "early_exit": True,
                    }
                )
                break
            if early_exit_min_profit_factor is not None and _metric_value(best, "profit_factor") < float(
                early_exit_min_profit_factor
            ):
                _log_window_skip(
                    wid,
                    len(windows),
                    f"early exit: selected in-sample profit_factor {_metric_value(best, 'profit_factor'):.2f} "
                    f"< {float(early_exit_min_profit_factor):.2f}",
                )
                rows.append(
                    _early_exit_row(
                        wid,
                        tr_s,
                        tr_e,
                        te_s,
                        te_e,
                        objective,
                        best,
                        "selected_train_profit_factor_below_minimum",
                    )
                )
                progress.update(wid, force=True)
                window_timings.append(
                    {
                        "window_id": wid,
                        "slice_seconds": slice_seconds,
                        "train_grid_seconds": train_grid_seconds,
                        "total_seconds": _elapsed(window_started),
                        "early_exit": True,
                    }
                )
                break
            write_started = time.perf_counter()
            if reused_train_grid:
                reused_train_grid_count += 1
                train_grid_paths.append(str(train_grid_path))
            else:
                written_train_grid_path = _write_window_train_grid(
                    grid_df,
                    train_grid_dir,
                    wid,
                    tr_s,
                    tr_e,
                    te_s,
                    te_e,
                    objective,
                    base_config,
                    train_grid_metadata,
                )
                if written_train_grid_path:
                    train_grid_paths.append(written_train_grid_path)
            train_grid_write_seconds = _elapsed(write_started)
            _add_timing(phase_timings, "train_grid_write", train_grid_write_seconds)

            param_cols = list(grid_config.get("parameters", {}).keys())
            params = {k: best[k].item() if hasattr(best[k], "item") else best[k] for k in param_cols}
            train_objective = _metric_value(best, objective)
            oos_started = time.perf_counter()
            test_cfg = apply_dotted_params(base_config, params)
            test_result = run_research_backtest(
                test_cfg,
                test,
                detail_data=test_detail,
                bar_engine_cls=BacktestEngine,
            )
            oos_seconds = _elapsed(oos_started)
            _add_timing(phase_timings, "oos_backtest", oos_seconds)
            test_metrics = test_result["metrics"]
            if include_trade_log:
                annotate_started = time.perf_counter()
                trade_frames.append(
                    _annotate_oos_trades(
                        test_result.get("trades", pd.DataFrame()),
                        wid,
                        tr_s,
                        tr_e,
                        te_s,
                        te_e,
                        objective,
                        train_objective,
                        params,
                    )
                )
                _add_timing(phase_timings, "annotate_oos_trades", _elapsed(annotate_started))
            passed, _ = benchmark(test_metrics, benchmarks)
            rows.append(
                {
                    "window_id": wid,
                    "train_start": tr_s,
                    "train_end": tr_e,
                    "test_start": te_s,
                    "test_end": te_e,
                    "objective": _objective_label(objective),
                    "train_objective": train_objective,
                    "selected_params": params,
                    "train_mar": _metric_value(best, "mar"),
                    "train_cagr": _metric_value(best, "cagr"),
                    "train_max_drawdown_pct": _metric_value(best, "max_drawdown_pct"),
                    "train_net_profit": _metric_value(best, "net_profit"),
                    "train_profit_factor": _metric_value(best, "profit_factor"),
                    "train_max_drawdown": _metric_value(best, "max_drawdown"),
                    "test_mar": _metric_value(test_metrics, "mar"),
                    "test_cagr": _metric_value(test_metrics, "cagr"),
                    "test_max_drawdown_pct": _metric_value(test_metrics, "max_drawdown_pct"),
                    "test_net_profit": _metric_value(test_metrics, "net_profit"),
                    "test_profit_factor": _metric_value(test_metrics, "profit_factor"),
                    "test_max_drawdown": _metric_value(test_metrics, "max_drawdown"),
                    "test_trades": int(_metric_value(test_metrics, "total_trades")),
                    "test_passed": passed,
                }
            )
            _log_window_result(wid, len(windows), objective, params, best, test_metrics)
            progress.update(wid, force=True, detail=_progress_detail(test_metrics))
            window_timings.append(
                {
                    "window_id": wid,
                    "slice_seconds": slice_seconds,
                    "train_grid_seconds": train_grid_seconds,
                    "train_grid_write_seconds": train_grid_write_seconds,
                    "oos_backtest_seconds": oos_seconds,
                    "total_seconds": _elapsed(window_started),
                    "reused_train_grid": reused_train_grid,
                }
            )
    finally:
        if pooled_executor is not None:
            pooled_executor.shutdown()
    df = pd.DataFrame(rows)
    stitch_started = time.perf_counter()
    trades = _stitch_oos_trades(trade_frames) if include_trade_log else None
    if include_trade_log:
        _add_timing(phase_timings, "stitch_oos_trades", _elapsed(stitch_started))
    summary = {
        "windows": int(len(df)),
        "parameter_mode": "fixed_config" if not grid_config["parameters"] else "predeclared_optimization",
        "objective": _objective_label(objective),
        "window_mode": _wfa_mode(wfa_config),
        "train_months": int(wfa_config.get("train_months", 3)),
        "test_months": int(wfa_config.get("test_months", 1)),
        "step_months": int(wfa_config["step_months"])
        if "step_months" in wfa_config
        else int(wfa_config.get("test_months", 1)),
        "parallel": _wfa_parallel_config(wfa_config),
        "selection_filter": selection_filter,
        "early_exit_min_train_profit_factor": float(early_exit_min_profit_factor)
        if early_exit_min_profit_factor is not None
        else None,
        "early_exit_require_train_profitable": early_exit_require_train_profitable,
        "early_exit": bool(len(df) and "early_exit" in df.columns and df["early_exit"].fillna(False).any()),
        "passing_windows": int(df["test_passed"].sum()) if len(df) else 0,
        "profitable_windows": int((df["test_net_profit"] > 0).sum()) if len(df) else 0,
        "profitable_window_rate": float((df["test_net_profit"] > 0).mean()) if len(df) else 0.0,
        "meets_profitable_window_benchmark": (
            float((df["test_net_profit"] > 0).mean()) >= benchmarks.get("min_wfa_profitable_window_rate", 0.0)
            if len(df)
            else False
        ),
        "median_test_net_profit": float(df["test_net_profit"].median()) if len(df) else 0.0,
        "median_test_mar": _summary_median(df, "test_mar"),
        "median_test_cagr": _summary_median(df, "test_cagr"),
        "median_test_max_drawdown_pct": _summary_median(df, "test_max_drawdown_pct"),
        "train_grid_reports_retained": train_grid_dir is not None,
        "train_grid_report_files": train_grid_paths,
        "reuse_existing_train_grids_requested": reuse_existing_train_grids,
        "reused_existing_train_grids": reused_train_grid_count > 0,
        "reused_train_grid_count": reused_train_grid_count,
        "strict_train_grid_reuse": strict_train_grid_reuse,
        "phase_timings_seconds": _round_timing_dict(phase_timings),
        "window_timings_seconds": [_round_timing_dict(item) for item in window_timings],
    }
    if include_trade_log:
        summary["stitched_oos_trades"] = int(len(trades))
        return df, summary, trades
    return df, summary


def _early_exit_row(
    window_id: int,
    train_start,
    train_end,
    test_start,
    test_end,
    objective: str,
    best,
    reason: str,
) -> dict:
    return {
        "window_id": window_id,
        "train_start": train_start,
        "train_end": train_end,
        "test_start": test_start,
        "test_end": test_end,
        "objective": _objective_label(objective),
        "train_objective": _metric_value(best, objective),
        "selected_params": {},
        "train_mar": _metric_value(best, "mar"),
        "train_cagr": _metric_value(best, "cagr"),
        "train_max_drawdown_pct": _metric_value(best, "max_drawdown_pct"),
        "train_net_profit": _metric_value(best, "net_profit"),
        "train_profit_factor": _metric_value(best, "profit_factor"),
        "train_max_drawdown": _metric_value(best, "max_drawdown"),
        "test_mar": 0.0,
        "test_cagr": 0.0,
        "test_max_drawdown_pct": 0.0,
        "test_net_profit": 0.0,
        "test_profit_factor": 0.0,
        "test_max_drawdown": 0.0,
        "test_trades": 0,
        "test_passed": False,
        "early_exit": True,
        "early_exit_reason": reason,
    }


def _elapsed(started_at: float) -> float:
    return time.perf_counter() - started_at


def _add_timing(timings: dict[str, float], key: str, seconds: float) -> None:
    timings[key] = timings.get(key, 0.0) + float(seconds)


def _round_timing_dict(values: dict) -> dict:
    return {
        key: (
            round(float(value), 6)
            if not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(float(value))
            else value
        )
        for key, value in values.items()
    }


def _annotate_oos_trades(
    trades: pd.DataFrame,
    window_id: int,
    train_start,
    train_end,
    test_start,
    test_end,
    objective: str,
    train_objective: float,
    params: dict,
) -> pd.DataFrame:
    if trades is None or trades.empty:
        return pd.DataFrame()

    out = trades.copy().reset_index(drop=True)
    if "trade_id" in out.columns:
        source_trade_id = out["trade_id"]
        out = out.drop(columns=["trade_id"])
        out.insert(0, "source_trade_id", source_trade_id)

    metadata = pd.DataFrame(
        {
            "wfa_window_id": [window_id] * len(out),
            "wfa_train_start": [_date_string(train_start)] * len(out),
            "wfa_train_end": [_date_string(train_end)] * len(out),
            "wfa_test_start": [_date_string(test_start)] * len(out),
            "wfa_test_end": [_date_string(test_end)] * len(out),
            "wfa_objective": [_objective_label(objective)] * len(out),
            "wfa_train_objective": [train_objective] * len(out),
            "wfa_selected_params": [dict(params)] * len(out),
        }
    )
    return pd.concat([metadata, out], axis=1)


def _stitch_oos_trades(frames: list[pd.DataFrame]) -> pd.DataFrame:
    non_empty = [frame for frame in frames if frame is not None and not frame.empty]
    if not non_empty:
        return pd.DataFrame(columns=_stitched_oos_trade_columns())

    out = pd.concat(non_empty, ignore_index=True)
    sort_columns = [
        column
        for column in ["entry_timestamp", "exit_timestamp", "session_date", "wfa_window_id", "source_trade_id"]
        if column in out.columns
    ]
    if sort_columns:
        out = out.sort_values(sort_columns, kind="stable").reset_index(drop=True)
    out.insert(0, "trade_id", range(1, len(out) + 1))
    return out


def _stitched_oos_trade_columns() -> list[str]:
    return [
        "trade_id",
        "wfa_window_id",
        "wfa_train_start",
        "wfa_train_end",
        "wfa_test_start",
        "wfa_test_end",
        "wfa_objective",
        "wfa_train_objective",
        "wfa_selected_params",
        "source_trade_id",
        "session_date",
        "net_pnl",
        "contracts",
    ]


def _clear_window_train_grid_reports(train_grid_dir: str | Path) -> None:
    out = Path(train_grid_dir)
    out.mkdir(parents=True, exist_ok=True)
    for path in out.glob("window_*_train_grid.csv"):
        if path.is_file():
            path.unlink()


def _existing_window_train_grid(train_grid_dir: str | Path | None, window_id: int) -> Path | None:
    if train_grid_dir is None:
        return None
    path = Path(train_grid_dir) / f"window_{window_id:03d}_train_grid.csv"
    return path if path.is_file() else None


def _read_reusable_window_train_grid(
    path: Path,
    window_id: int,
    train_start,
    train_end,
    test_start,
    test_end,
    objective: str,
    grid_config: dict,
    metadata: dict,
    *,
    strict: bool,
) -> pd.DataFrame | None:
    grid_df = pd.read_csv(path)
    reason = _train_grid_reuse_validation_error(
        grid_df,
        window_id,
        train_start,
        train_end,
        test_start,
        test_end,
        objective,
        grid_config,
        metadata,
    )
    if not reason:
        return grid_df
    message = f"existing WFA train grid {path} is not reusable: {reason}"
    if strict:
        raise ValueError(message)
    print(f"walk-forward {window_id} ignoring {message}", flush=True)
    return None


def _train_grid_reuse_validation_error(
    grid_df: pd.DataFrame,
    window_id: int,
    train_start,
    train_end,
    test_start,
    test_end,
    objective: str,
    grid_config: dict,
    metadata: dict,
) -> str | None:
    if grid_df.empty:
        return "file is empty"
    expected_values = {
        "wfa_window_id": str(window_id),
        "wfa_train_start": _date_string(train_start),
        "wfa_train_end": _date_string(train_end),
        "wfa_test_start": _date_string(test_start),
        "wfa_test_end": _date_string(test_end),
        "wfa_objective": _objective_label(objective),
        "wfa_base_config_hash": metadata["base_config_hash"],
        "wfa_parameter_hash": metadata["parameter_hash"],
        "wfa_selection_filter_hash": metadata["selection_filter_hash"],
    }
    if metadata.get("input_hash"):
        expected_values["wfa_input_hash"] = metadata["input_hash"]
    for column, expected in expected_values.items():
        if column not in grid_df.columns:
            return f"missing metadata column {column}"
        actual_values = {_normalise_reuse_value(value) for value in grid_df[column].dropna().unique()}
        if actual_values != {str(expected)}:
            return f"{column} mismatch: expected {expected}, found {sorted(actual_values)}"
    missing_params = sorted(set(grid_config.get("parameters", {})) - set(grid_df.columns))
    if missing_params:
        return f"missing parameter column(s) {missing_params}"
    return None


def _normalise_reuse_value(value) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _write_window_train_grid(
    grid_df: pd.DataFrame,
    train_grid_dir: str | Path | None,
    window_id: int,
    train_start,
    train_end,
    test_start,
    test_end,
    objective: str,
    base_config: dict,
    metadata: dict,
) -> str | None:
    if train_grid_dir is None:
        return None

    path = Path(train_grid_dir) / f"window_{window_id:03d}_train_grid.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    annotated = _annotate_train_grid(
        grid_df,
        window_id,
        train_start,
        train_end,
        test_start,
        test_end,
        objective,
        metadata,
    )
    write_report_csv(annotated, path, market_timezone(base_config), index=False)
    return str(path)


def _annotate_train_grid(
    grid_df: pd.DataFrame,
    window_id: int,
    train_start,
    train_end,
    test_start,
    test_end,
    objective: str,
    metadata_values: dict,
) -> pd.DataFrame:
    sort_columns, ascending = _selection_sort_spec(grid_df, objective)
    out = grid_df.sort_values(sort_columns, ascending=ascending, na_position="last").reset_index(drop=True)
    ranks = list(range(1, len(out) + 1))
    metadata = pd.DataFrame(
        {
            "wfa_window_id": [window_id] * len(out),
            "wfa_train_start": [_date_string(train_start)] * len(out),
            "wfa_train_end": [_date_string(train_end)] * len(out),
            "wfa_test_start": [_date_string(test_start)] * len(out),
            "wfa_test_end": [_date_string(test_end)] * len(out),
            "wfa_objective": [_objective_label(objective)] * len(out),
            "wfa_base_config_hash": [metadata_values["base_config_hash"]] * len(out),
            "wfa_parameter_hash": [metadata_values["parameter_hash"]] * len(out),
            "wfa_selection_filter_hash": [metadata_values["selection_filter_hash"]] * len(out),
            "wfa_input_hash": [metadata_values.get("input_hash") or ""] * len(out),
            "wfa_selection_rank": ranks,
            "wfa_selected": [rank == 1 for rank in ranks],
        }
    )
    return pd.concat([metadata, out], axis=1)


def _date_string(value) -> str:
    return pd.Timestamp(value).date().isoformat()


def _train_grid_metadata(base_config: dict, grid_config: dict, input_hash: str | None) -> dict:
    return {
        "base_config_hash": object_sha256(base_config),
        "parameter_hash": object_sha256(grid_config.get("parameters", {})),
        "selection_filter_hash": object_sha256(grid_config.get("selection_filter", {})),
        "input_hash": input_hash,
    }


def _start_wfa_grid_pool(
    data: pd.DataFrame,
    detail_data: pd.DataFrame | None,
    base_config: dict,
    benchmarks: dict,
    grid_config: dict,
) -> ProcessPoolExecutor | None:
    if not _use_pooled_wfa_grid(grid_config):
        return None
    workers = _pooled_wfa_workers(grid_config)
    return ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_wfa_grid_worker,
        initargs=(data, detail_data, base_config, benchmarks),
    )


def _use_pooled_wfa_grid(grid_config: dict) -> bool:
    parallel = grid_config.get("parallel") or {}
    if parallel.get("scope") != "window_grid":
        return False
    combo_count = len(parameter_combinations(grid_config.get("parameters", {}), "wfa.parameters"))
    return bool(parallel.get("enabled", False)) and _pooled_wfa_workers(grid_config) > 1 and combo_count > 1


def _pooled_wfa_workers(grid_config: dict) -> int:
    parallel = grid_config.get("parallel") or {}
    requested = int(parallel.get("workers") or os.cpu_count() or 1)
    max_cpus = os.cpu_count() or requested
    return max(1, min(requested, max_cpus))


def _run_pooled_window_train_grid(
    executor: ProcessPoolExecutor,
    window_id: int,
    total_windows: int,
    train_start,
    train_end,
    combos: list[dict],
    workers: int,
) -> pd.DataFrame:
    progress = progress_bar(len(combos), f"walk-forward {window_id}/{total_windows} train grid")
    futures = {
        executor.submit(_run_wfa_grid_batch_worker, train_start, train_end, batch): len(batch)
        for batch in _combo_batches(combos, workers)
    }
    rows = []
    completed = 0
    for future in as_completed(futures):
        rows.extend(future.result())
        completed += futures[future]
        progress.update(completed)
    return pd.DataFrame(rows).sort_values("run_id").reset_index(drop=True)


def _init_wfa_grid_worker(
    data: pd.DataFrame,
    detail_data: pd.DataFrame | None,
    base_config: dict,
    benchmarks: dict,
) -> None:
    global _WFA_WORKER_DATA, _WFA_WORKER_DETAIL_DATA, _WFA_WORKER_BASE_CONFIG, _WFA_WORKER_BENCHMARKS
    global _WFA_WORKER_SLICE_CACHE
    _WFA_WORKER_DATA = data
    _WFA_WORKER_DETAIL_DATA = detail_data
    _WFA_WORKER_BASE_CONFIG = base_config
    _WFA_WORKER_BENCHMARKS = benchmarks
    _WFA_WORKER_SLICE_CACHE = {}


def _run_wfa_grid_batch_worker(train_start, train_end, batch: list[tuple[int, dict]]) -> list[dict]:
    if _WFA_WORKER_DATA is None or _WFA_WORKER_BASE_CONFIG is None or _WFA_WORKER_BENCHMARKS is None:
        raise RuntimeError("WFA grid worker was not initialized.")
    train, train_detail = _wfa_worker_train_slice(train_start, train_end)
    rows = []
    for run_id, combo in batch:
        row, _, _ = _evaluate_core_grid_combo(
            train,
            _WFA_WORKER_BASE_CONFIG,
            _WFA_WORKER_BENCHMARKS,
            run_id,
            combo,
            include_reports=False,
            detail_data=train_detail,
        )
        rows.append(row)
    return rows


def _wfa_worker_train_slice(train_start, train_end) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    if _WFA_WORKER_SLICE_CACHE is None:
        raise RuntimeError("WFA grid worker slice cache was not initialized.")
    key = (_date_string(train_start), _date_string(train_end))
    if key not in _WFA_WORKER_SLICE_CACHE:
        train = _slice(_WFA_WORKER_DATA, train_start, train_end)
        train_detail = _slice(_WFA_WORKER_DETAIL_DATA, train_start, train_end) if _WFA_WORKER_DETAIL_DATA is not None else None
        _WFA_WORKER_SLICE_CACHE[key] = (train, train_detail)
    return _WFA_WORKER_SLICE_CACHE[key]


def _combo_batches(combos: list[dict], workers: int) -> list[list[tuple[int, dict]]]:
    indexed = list(enumerate(combos, start=1))
    if not indexed:
        return []
    chunk_size = _parallel_chunk_size(len(indexed), workers)
    return [indexed[start : start + chunk_size] for start in range(0, len(indexed), chunk_size)]


def _parallel_chunk_size(item_count: int, workers: int) -> int:
    if item_count <= 0:
        return 1
    target_chunks = max(1, int(workers) * 4)
    return max(1, min(32, math.ceil(item_count / target_chunks)))


def _wfa_grid_config(wfa_config: dict) -> dict:
    if "parameters" not in wfa_config:
        raise ValueError(
            "wfa.parameters must be declared; use an empty mapping for one fixed configuration."
        )
    if not isinstance(wfa_config["parameters"], dict):
        raise ValueError("wfa.parameters must be a mapping.")
    return {
        "objective": _wfa_objective(wfa_config.get("objective", "MAR")),
        "parameters": wfa_config["parameters"],
        "parallel": _wfa_parallel_config(wfa_config),
        "selection_filter": _wfa_selection_filter(wfa_config),
    }


def _wfa_parallel_config(wfa_config: dict) -> dict:
    parallel = wfa_config.get("parallel") or {}
    if isinstance(parallel, bool):
        return {"enabled": parallel, "scope": "grid"}
    if not isinstance(parallel, dict):
        raise ValueError("wfa.parallel must be a boolean or mapping.")
    scope = str(parallel.get("scope", "grid")).lower()
    if scope not in {"grid", "window_grid"}:
        raise ValueError("wfa.parallel.scope must be 'grid' or 'window_grid'.")
    out = {
        "enabled": bool(parallel.get("enabled", False)),
        "scope": scope,
    }
    if "workers" in parallel:
        out["workers"] = int(parallel["workers"])
    return out


def _wfa_objective(value) -> str:
    key = str(value).strip().lower()
    if key not in _WFA_OBJECTIVES:
        raise ValueError("wfa.objective must be one of: net_profit, MAR, profit_factor.")
    return _WFA_OBJECTIVES[key]


def _objective_label(objective: str) -> str:
    return _OBJECTIVE_LABELS.get(objective, objective)


def _select_best_in_sample(grid_df: pd.DataFrame, objective: str, selection_filter: dict | None = None):
    if objective not in grid_df.columns:
        raise ValueError(f"wfa.objective '{_objective_label(objective)}' is not available in grid results.")

    candidates = _apply_selection_filter(grid_df, selection_filter or {})
    if candidates.empty:
        raise NoEligibleWfaSelectionError("no in-sample grid row satisfies the configured selection_filter")
    sort_columns, ascending = _selection_sort_spec(candidates, objective)
    return candidates.sort_values(sort_columns, ascending=ascending, na_position="last").iloc[0]


def _selection_sort_spec(grid_df: pd.DataFrame, objective: str) -> tuple[list[str], list[bool]]:
    sort_columns: list[str] = []
    ascending: list[bool] = []
    for column, asc in [
        (objective, False),
        ("cagr", False),
        ("max_drawdown_pct", True),
        ("net_profit", False),
        ("max_drawdown", True),
        ("run_id", True),
    ]:
        if column in grid_df.columns and column not in sort_columns:
            sort_columns.append(column)
            ascending.append(asc)
    return sort_columns, ascending


def _wfa_selection_filter(wfa_config: dict) -> dict:
    configured = dict(wfa_config.get("selection_filter") or {})
    for source, target in [
        ("selection_min_trades_per_year", "min_trades_per_year"),
        ("selection_exclusive_min_trades_per_year", "exclusive_min_trades_per_year"),
        ("selection_min_total_trades", "min_total_trades"),
        ("selection_min_profit_factor", "min_profit_factor"),
    ]:
        if source in wfa_config and target not in configured:
            configured[target] = wfa_config[source]
    return configured


def _apply_selection_filter(grid_df: pd.DataFrame, selection_filter: dict) -> pd.DataFrame:
    candidates = grid_df
    filters = [
        ("total_trades", "min_total_trades", lambda series, value: series >= value),
        ("trades_per_year", "min_trades_per_year", lambda series, value: series >= value),
        ("trades_per_year", "exclusive_min_trades_per_year", lambda series, value: series > value),
        ("profit_factor", "min_profit_factor", lambda series, value: series >= value),
    ]
    for column, key, predicate in filters:
        if key not in selection_filter:
            continue
        if column not in candidates.columns:
            return candidates.iloc[0:0].copy()
        candidates = candidates[predicate(pd.to_numeric(candidates[column], errors="coerce"), float(selection_filter[key]))]
    return candidates


def _log_window_start(
    window_id: int,
    total_windows: int,
    train_start,
    train_end,
    test_start,
    test_end,
    train_rows: int,
    test_rows: int,
) -> None:
    print(
        "\n"
        f"walk-forward {window_id}/{total_windows} start | "
        f"in-sample {_format_period(train_start, train_end)} ({train_rows:,} bars) | "
        f"out-of-sample {_format_period(test_start, test_end)} ({test_rows:,} bars)",
        flush=True,
    )


def _log_window_result(
    window_id: int,
    total_windows: int,
    objective: str,
    params: dict,
    best,
    test_metrics: dict,
) -> None:
    objective_value = _metric_value(best, objective)
    print(
        f"walk-forward {window_id}/{total_windows} complete | "
        f"objective={_objective_label(objective)} train_objective={_format_metric(objective_value)} | "
        f"selected_params={_format_params(params)} | "
        f"train_mar={_format_metric(_metric_value(best, 'mar'))} "
        f"train_cagr={_format_percent(_metric_value(best, 'cagr'))} "
        f"train_max_dd_pct={_format_percent(_metric_value(best, 'max_drawdown_pct'))} "
        f"train_net_profit={_format_metric(_metric_value(best, 'net_profit'))} | "
        f"oos_mar={_format_metric(_metric_value(test_metrics, 'mar'))} "
        f"oos_cagr={_format_percent(_metric_value(test_metrics, 'cagr'))} "
        f"oos_max_dd_pct={_format_percent(_metric_value(test_metrics, 'max_drawdown_pct'))} "
        f"oos_net_profit={_format_metric(_metric_value(test_metrics, 'net_profit'))}",
        flush=True,
    )


def _log_window_skip(window_id: int, total_windows: int, reason: str) -> None:
    print(f"walk-forward {window_id}/{total_windows} skipped | reason={reason}", flush=True)


def _format_period(start, end) -> str:
    return f"{pd.Timestamp(start).date()} -> {pd.Timestamp(end).date()}"


def _format_params(params: dict) -> str:
    return ", ".join(f"{key}={_format_param_value(value)}" for key, value in params.items())


def _format_param_value(value) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _format_metric(value) -> str:
    numeric = _to_float(value)
    return f"{numeric:,.2f}"


def _format_percent(value) -> str:
    numeric = _to_float(value)
    if not math.isfinite(numeric):
        return str(numeric)
    return f"{numeric * 100:,.2f}%"


def _metric_value(source, key: str, default: float = 0.0) -> float:
    if isinstance(source, dict):
        value = source.get(key, default)
    else:
        value = source[key] if key in source else default
    return _to_float(value)


def _to_float(value) -> float:
    if hasattr(value, "item"):
        value = value.item()
    if pd.isna(value):
        return 0.0
    return float(value)


def _summary_median(df: pd.DataFrame, column: str):
    if not len(df) or column not in df:
        return 0.0
    value = _to_float(df[column].median())
    return value if math.isfinite(value) else None


def _progress_detail(test_metrics: dict) -> str:
    return (
        f"last OOS MAR={_format_metric(_metric_value(test_metrics, 'mar'))} "
        f"CAGR={_format_percent(_metric_value(test_metrics, 'cagr'))} "
        f"DD={_format_percent(_metric_value(test_metrics, 'max_drawdown_pct'))} "
        f"NP={_format_metric(_metric_value(test_metrics, 'net_profit'))}"
    )


def _wfa_mode(wfa_config: dict) -> str:
    return str(wfa_config.get("mode", "unanchored")).lower()


def _validate_window_config(train_months: int, test_months: int, step_months: int, mode: str) -> None:
    if train_months <= 0:
        raise ValueError("wfa.train_months must be greater than zero.")
    if test_months <= 0:
        raise ValueError("wfa.test_months must be greater than zero.")
    if step_months <= 0:
        raise ValueError("wfa.step_months must be greater than zero.")
    if mode not in {"anchored", "unanchored"}:
        raise ValueError("wfa.mode must be 'anchored' or 'unanchored'.")
