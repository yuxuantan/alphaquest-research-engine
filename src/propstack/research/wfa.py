from __future__ import annotations

import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.backtest.metrics import benchmark
from propstack.research.core_grid import run_core_grid
from propstack.utils.params import apply_dotted_params
from propstack.utils.progress import progress_bar


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


def run_wfa(data: pd.DataFrame, base_config: dict, wfa_config: dict, benchmarks: dict):
    rows = []
    grid_config = _wfa_grid_config(wfa_config)
    windows = list(
        create_windows(
            data,
            int(wfa_config.get("train_months", 3)),
            int(wfa_config.get("test_months", 1)),
            int(wfa_config["step_months"]) if "step_months" in wfa_config else None,
            _wfa_mode(wfa_config),
        )
    )
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
        best = grid_df.sort_values("net_profit", ascending=False).iloc[0]
        param_cols = list(grid_config.get("parameters", {}).keys())
        params = {k: best[k].item() if hasattr(best[k], "item") else best[k] for k in param_cols}
        test_cfg = apply_dotted_params(base_config, params)
        test_result = BacktestEngine(test_cfg).run(test)
        test_metrics = test_result["metrics"]
        passed, _ = benchmark(test_metrics, benchmarks)
        rows.append(
            {
                "window_id": wid,
                "train_start": tr_s,
                "train_end": tr_e,
                "test_start": te_s,
                "test_end": te_e,
                "selected_params": params,
                "train_net_profit": float(best["net_profit"]),
                "train_profit_factor": float(best["profit_factor"]),
                "train_max_drawdown": float(best["max_drawdown"]),
                "test_net_profit": test_metrics["net_profit"],
                "test_profit_factor": test_metrics["profit_factor"],
                "test_max_drawdown": test_metrics["max_drawdown"],
                "test_trades": test_metrics["total_trades"],
                "test_passed": passed,
            }
        )
        _log_window_result(wid, len(windows), grid_config.get("objective", "net_profit"), params, best, test_metrics)
        progress.update(wid, force=True)
    df = pd.DataFrame(rows)
    summary = {
        "windows": int(len(df)),
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
    }
    return df, summary


def _wfa_grid_config(wfa_config: dict) -> dict:
    if "parameters" not in wfa_config:
        raise ValueError("wfa.parameters must define the walk-forward optimization parameter space.")
    return {
        "objective": wfa_config.get("objective", "net_profit"),
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
    objective_value = best[objective] if objective in best else best["net_profit"]
    print(
        f"walk-forward {window_id}/{total_windows} complete | "
        f"objective={objective} train_objective={_format_metric(objective_value)} | "
        f"selected_params={_format_params(params)} | "
        f"oos_net_profit={_format_metric(test_metrics['net_profit'])} | "
        f"oos_max_drawdown={_format_metric(test_metrics['max_drawdown'])}",
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
    numeric = float(value.item() if hasattr(value, "item") else value)
    return f"{numeric:,.2f}"


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
