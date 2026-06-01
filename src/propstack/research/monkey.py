from __future__ import annotations

import random
import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.backtest.metrics import benchmark, calculate_metrics
from propstack.utils.params import apply_dotted_params
from propstack.utils.progress import progress_bar


def _sample(rng: random.Random, bounds):
    lo, hi = bounds
    if isinstance(lo, int) and isinstance(hi, int):
        return rng.randint(lo, hi)
    return rng.uniform(float(lo), float(hi))


def stress_trades(trades: pd.DataFrame, rng: random.Random, stress_cfg: dict) -> pd.DataFrame:
    if trades.empty:
        return trades
    out = trades.copy()
    skip_p = rng.uniform(*stress_cfg.get("skip_trade_probability", [0.0, 0.0]))
    skip_win_p = rng.uniform(*stress_cfg.get("skip_winning_trade_probability", [0.0, 0.0]))
    keep = []
    for _, row in out.iterrows():
        if rng.random() < skip_p:
            keep.append(False)
        elif row["net_pnl"] > 0 and rng.random() < skip_win_p:
            keep.append(False)
        else:
            keep.append(True)
    out = out.loc[keep].copy()
    if out.empty:
        return out
    extra_slip = rng.uniform(*stress_cfg.get("extra_slippage_ticks", [0.0, 0.0]))
    comm_mult = rng.uniform(*stress_cfg.get("commission_multiplier", [1.0, 1.0]))
    out["net_pnl"] = out["gross_pnl"] - (out["commission"] * comm_mult) - out["slippage_cost"] - extra_slip
    return out


def run_monkey(data: pd.DataFrame, base_config: dict, monkey_config: dict, benchmarks: dict) -> tuple[pd.DataFrame, dict]:
    rng = random.Random(monkey_config.get("seed", 1))
    rows = []
    total_runs = int(monkey_config.get("runs", 100))
    progress = progress_bar(total_runs, "monkey runs")
    for run_id in range(1, total_runs + 1):
        sampled = {k: _sample(rng, v) for k, v in monkey_config.get("parameter_ranges", {}).items()}
        cfg = apply_dotted_params(base_config, sampled)
        result = BacktestEngine(cfg).run(data)
        trades = stress_trades(result["trades"], rng, monkey_config.get("stress", {}))
        metrics = calculate_metrics(
            trades,
            initial_balance=float(base_config.get("backtest", {}).get("initial_balance", 0)),
        )
        passed, reason = benchmark(metrics, benchmarks)
        rows.append(
            {
                "run_id": run_id,
                **sampled,
                "net_profit": metrics["net_profit"],
                "max_drawdown": metrics["max_drawdown"],
                "profit_factor": metrics["profit_factor"],
                "expectancy": metrics["expectancy_r"],
                "benchmark_passed": passed,
                "failure_reason": reason,
            }
        )
        progress.update(run_id)
    df = pd.DataFrame(rows)
    summary = {
        "number_of_runs": int(len(df)),
        "percentage_profitable": float((df["net_profit"] > 0).mean()) if len(df) else 0.0,
        "percentage_passing_benchmark": float(df["benchmark_passed"].mean()) if len(df) else 0.0,
        "median_net_profit": float(df["net_profit"].median()) if len(df) else 0.0,
        "p5_net_profit": float(df["net_profit"].quantile(0.05)) if len(df) else 0.0,
        "median_max_drawdown": float(df["max_drawdown"].median()) if len(df) else 0.0,
        "p95_max_drawdown": float(df["max_drawdown"].quantile(0.95)) if len(df) else 0.0,
    }
    return df, summary
