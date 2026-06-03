from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.backtest.metrics import benchmark
from propstack.research.core_grid import run_core_grid
from propstack.utils.params import apply_dotted_params
from propstack.utils.progress import progress_bar
from propstack.utils.reports import market_timezone, write_report_csv

_WFA_OBJECTIVES = {
    "net_profit": "net_profit",
    "net profit": "net_profit",
    "net-profit": "net_profit",
    "mar": "mar",
}

_OBJECTIVE_LABELS = {
    "net_profit": "net_profit",
    "mar": "MAR",
}


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
):
    rows = []
    trade_frames = []
    train_grid_paths = []
    grid_config = _wfa_grid_config(wfa_config)
    objective = grid_config["objective"]
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
        _clear_window_train_grid_reports(train_grid_dir)
    progress = progress_bar(len(windows), "walk-forward windows", show_timing=True)
    progress.update(0, force=True)
    for wid, (tr_s, tr_e, te_s, te_e) in enumerate(windows, start=1):
        train = _slice(data, tr_s, tr_e)
        test = _slice(data, te_s, te_e)
        _log_window_start(wid, len(windows), tr_s, tr_e, te_s, te_e, len(train), len(test))
        if train.empty or test.empty:
            _log_window_skip(wid, len(windows), "empty train/test slice")
            progress.update(wid, force=True)
            continue
        grid_df, _ = run_core_grid(train, base_config, grid_config, benchmarks, parameter_label="wfa.parameters")
        if grid_df.empty:
            _log_window_skip(wid, len(windows), "no in-sample grid results")
            progress.update(wid, force=True)
            continue
        best = _select_best_in_sample(grid_df, objective)
        train_grid_path = _write_window_train_grid(
            grid_df,
            train_grid_dir,
            wid,
            tr_s,
            tr_e,
            te_s,
            te_e,
            objective,
            base_config,
        )
        if train_grid_path:
            train_grid_paths.append(train_grid_path)
        param_cols = list(grid_config.get("parameters", {}).keys())
        params = {k: best[k].item() if hasattr(best[k], "item") else best[k] for k in param_cols}
        train_objective = _metric_value(best, objective)
        test_cfg = apply_dotted_params(base_config, params)
        test_result = BacktestEngine(test_cfg).run(test)
        test_metrics = test_result["metrics"]
        if include_trade_log:
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
    df = pd.DataFrame(rows)
    summary = {
        "windows": int(len(df)),
        "objective": _objective_label(objective),
        "window_mode": _wfa_mode(wfa_config),
        "train_months": int(wfa_config.get("train_months", 3)),
        "test_months": int(wfa_config.get("test_months", 1)),
        "step_months": int(wfa_config["step_months"])
        if "step_months" in wfa_config
        else int(wfa_config.get("test_months", 1)),
        "parallel": _wfa_parallel_config(wfa_config),
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
    }
    if include_trade_log:
        trades = _stitch_oos_trades(trade_frames)
        summary["stitched_oos_trades"] = int(len(trades))
        return df, summary, trades
    return df, summary


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
            "wfa_selection_rank": ranks,
            "wfa_selected": [rank == 1 for rank in ranks],
        }
    )
    return pd.concat([metadata, out], axis=1)


def _date_string(value) -> str:
    return pd.Timestamp(value).date().isoformat()


def _wfa_grid_config(wfa_config: dict) -> dict:
    if "parameters" not in wfa_config:
        raise ValueError("wfa.parameters must define the walk-forward optimization parameter space.")
    return {
        "objective": _wfa_objective(wfa_config.get("objective", "net_profit")),
        "parameters": wfa_config["parameters"],
        "parallel": _wfa_parallel_config(wfa_config),
    }


def _wfa_parallel_config(wfa_config: dict) -> dict:
    parallel = wfa_config.get("parallel") or {}
    if isinstance(parallel, bool):
        return {"enabled": parallel, "scope": "grid"}
    if not isinstance(parallel, dict):
        raise ValueError("wfa.parallel must be a boolean or mapping.")
    scope = str(parallel.get("scope", "grid")).lower()
    if scope != "grid":
        raise ValueError("wfa.parallel.scope must be 'grid'.")
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
        raise ValueError("wfa.objective must be one of: net_profit, MAR.")
    return _WFA_OBJECTIVES[key]


def _objective_label(objective: str) -> str:
    return _OBJECTIVE_LABELS.get(objective, objective)


def _select_best_in_sample(grid_df: pd.DataFrame, objective: str):
    if objective not in grid_df.columns:
        raise ValueError(f"wfa.objective '{_objective_label(objective)}' is not available in grid results.")

    sort_columns, ascending = _selection_sort_spec(grid_df, objective)
    return grid_df.sort_values(sort_columns, ascending=ascending, na_position="last").iloc[0]


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
