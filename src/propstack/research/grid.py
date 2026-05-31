from __future__ import annotations

from itertools import product
import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.backtest.metrics import benchmark
from propstack.utils.progress import progress_bar


def parameter_combinations(params: dict) -> list[dict]:
    keys = list(params.keys())
    return [dict(zip(keys, values)) for values in product(*(params[k] for k in keys))]


def run_grid(data: pd.DataFrame, base_config: dict, grid_config: dict, benchmarks: dict) -> tuple[pd.DataFrame, dict]:
    rows = []
    combos = parameter_combinations(grid_config.get("parameters", {}))
    progress = progress_bar(len(combos), "grid search")
    for idx, combo in enumerate(combos, start=1):
        cfg = {
            **base_config,
            "strategy": {**base_config.get("strategy", {}), **combo},
        }
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
                "worst_day": metrics["worst_day"],
                "best_day_concentration": metrics["best_day_concentration"],
                "consecutive_losses": metrics["max_consecutive_losses"],
                "benchmark_passed": passed,
                "failure_reason": reason,
            }
        )
        progress.update(idx)
    df = pd.DataFrame(rows)
    passing = int(df["benchmark_passed"].sum()) if len(df) else 0
    top = df.sort_values(["benchmark_passed", "net_profit"], ascending=[False, False]).head(10)
    summary = {
        "total_combinations_tested": int(len(df)),
        "number_passing_benchmark": passing,
        "percentage_passing_benchmark": float(passing / len(df)) if len(df) else 0.0,
        "top_10_combinations": top.to_dict(orient="records"),
        "stable_parameter_zones": summarize_stability(df),
    }
    return df, summary


def summarize_stability(df: pd.DataFrame) -> dict:
    if df.empty or "benchmark_passed" not in df:
        return {}
    zones = {}
    for col in ["reclaim_window_bars", "target_r_multiple", "stop_offset_ticks", "max_trades_per_day"]:
        if col in df.columns:
            grouped = df.groupby(col)["benchmark_passed"].mean().sort_values(ascending=False)
            zones[col] = grouped.to_dict()
    return zones
