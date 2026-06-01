from __future__ import annotations

import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.backtest.metrics import benchmark
from propstack.research.grid import run_grid
from propstack.utils.params import apply_dotted_params
from propstack.utils.progress import progress_bar


def create_windows(data: pd.DataFrame, train_months: int, test_months: int, step_months: int):
    start = pd.Timestamp(data["timestamp"].min()).tz_localize(None).normalize()
    end = pd.Timestamp(data["timestamp"].max()).tz_localize(None).normalize()
    cur = start
    while True:
        train_start = cur
        train_end = train_start + pd.DateOffset(months=train_months)
        test_start = train_end
        test_end = test_start + pd.DateOffset(months=test_months)
        if test_start > end:
            break
        yield train_start, train_end, test_start, test_end
        cur = cur + pd.DateOffset(months=step_months)


def _slice(data: pd.DataFrame, start, end):
    naive = data["timestamp"].dt.tz_localize(None)
    return data[(naive >= start) & (naive < end)].copy()


def run_wfa(data: pd.DataFrame, base_config: dict, grid_config: dict, wfa_config: dict, benchmarks: dict):
    rows = []
    windows = list(
        create_windows(
            data,
            int(wfa_config.get("train_months", 3)),
            int(wfa_config.get("test_months", 1)),
            int(wfa_config.get("step_months", 1)),
        )
    )
    progress = progress_bar(len(windows), "walk-forward windows")
    for wid, (tr_s, tr_e, te_s, te_e) in enumerate(windows, start=1):
        train = _slice(data, tr_s, tr_e)
        test = _slice(data, te_s, te_e)
        if train.empty or test.empty:
            progress.update(wid)
            continue
        grid_df, _ = run_grid(train, base_config, grid_config, benchmarks)
        if grid_df.empty:
            progress.update(wid)
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
        progress.update(wid)
    df = pd.DataFrame(rows)
    summary = {
        "windows": int(len(df)),
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
