from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
import os
import random
import pandas as pd

from propstack.prop.rules import PropRules
from propstack.prop.simulator import simulate_prop_path
from propstack.utils.progress import progress_bar

_WORKER_TRADES = None
_WORKER_CFG = None
_WORKER_RULES = None


def _path_sample(trades: pd.DataFrame, rng: random.Random, cfg: dict) -> pd.DataFrame:
    if trades.empty:
        return trades
    out = trades.sample(frac=1, random_state=rng.randint(1, 10**9)).reset_index(drop=True)
    keep = []
    for _, row in out.iterrows():
        if rng.random() < cfg.get("skip_trade_probability", 0.0):
            keep.append(False)
        elif row["net_pnl"] > 0 and rng.random() < cfg.get("skip_winning_trade_probability", 0.0):
            keep.append(False)
        else:
            keep.append(True)
    out = out.loc[keep].copy()
    if cfg.get("cluster_losses", False) and not out.empty:
        out = pd.concat([out[out["net_pnl"] < 0], out[out["net_pnl"] >= 0]], ignore_index=True)
    adverse = float(cfg.get("adverse_slippage_per_trade", 0.0))
    if adverse:
        out["net_pnl"] = out["net_pnl"] - adverse
    return out


def run_monte_carlo(trades: pd.DataFrame, cfg: dict, rules: PropRules) -> tuple[pd.DataFrame, dict]:
    total_runs = int(cfg.get("runs", 1000))
    parallel = _parallel_settings(cfg, total_runs)
    if parallel["enabled"]:
        rows = _run_parallel_monte_carlo(trades, cfg, rules, total_runs, parallel["workers"])
    else:
        rows = []
        progress = progress_bar(total_runs, "monte carlo runs")
        for run_id in range(1, total_runs + 1):
            rows.append(_evaluate_monte_carlo_run(run_id, trades, cfg, rules))
            progress.update(run_id)
    df = pd.DataFrame(rows).sort_values("run_id").reset_index(drop=True)
    summary = {
        "number_of_runs": int(len(df)),
        "median_ending_balance": float(df["ending_balance"].median()) if len(df) else rules.starting_balance,
        "p5_ending_balance": float(df["ending_balance"].quantile(0.05)) if len(df) else rules.starting_balance,
        "p95_drawdown": float(df["max_drawdown"].quantile(0.95)) if len(df) else 0.0,
        "probability_account_breach": float(df["account_breached"].mean()) if len(df) else 0.0,
        "probability_payout_eligible": float(df["payout_eligible"].mean()) if len(df) else 0.0,
        "probability_profit_before_drawdown": float(df["profit_before_drawdown"].mean()) if len(df) else 0.0,
        "probability_net_profit_gt_0": float((df["net_pnl"] > 0).mean()) if len(df) else 0.0,
        "parallel": {
            "enabled": parallel["enabled"],
            "workers": parallel["workers"] if parallel["enabled"] else 1,
            "scope": "runs",
        },
    }
    summary["meets_prop_pass_chance_benchmark"] = (
        summary["probability_profit_before_drawdown"]
        >= float(cfg.get("min_monte_carlo_prop_pass_chance", 0.0))
    )
    return df, summary


def _run_parallel_monte_carlo(
    trades: pd.DataFrame,
    cfg: dict,
    rules: PropRules,
    total_runs: int,
    workers: int,
) -> list[dict]:
    rows = []
    progress = progress_bar(total_runs, "monte carlo runs")
    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_monte_carlo_worker,
        initargs=(trades, cfg, rules),
    ) as executor:
        futures = {executor.submit(_run_monte_carlo_worker, run_id): run_id for run_id in range(1, total_runs + 1)}
        for done, future in enumerate(as_completed(futures), start=1):
            rows.append(future.result())
            progress.update(done)
    return rows


def _init_monte_carlo_worker(trades: pd.DataFrame, cfg: dict, rules: PropRules) -> None:
    global _WORKER_TRADES, _WORKER_CFG, _WORKER_RULES
    _WORKER_TRADES = trades
    _WORKER_CFG = cfg
    _WORKER_RULES = rules


def _run_monte_carlo_worker(run_id: int) -> dict:
    if _WORKER_TRADES is None or _WORKER_CFG is None or _WORKER_RULES is None:
        raise RuntimeError("Monte Carlo worker was not initialized.")
    return _evaluate_monte_carlo_run(run_id, _WORKER_TRADES, _WORKER_CFG, _WORKER_RULES)


def _evaluate_monte_carlo_run(run_id: int, trades: pd.DataFrame, cfg: dict, rules: PropRules) -> dict:
    rng = random.Random(_run_seed(int(cfg.get("seed", 1)), run_id))
    path = _path_sample(trades, rng, cfg)
    return {"run_id": run_id, **simulate_prop_path(path, rules)}


def _parallel_settings(cfg: dict, run_count: int) -> dict:
    parallel = cfg.get("parallel") or {}
    if isinstance(parallel, bool):
        enabled = parallel
        requested_workers = os.cpu_count() or 1
        scope = "runs"
    elif isinstance(parallel, dict):
        enabled = bool(parallel.get("enabled", False))
        requested_workers = int(parallel.get("workers") or os.cpu_count() or 1)
        scope = str(parallel.get("scope", "runs")).lower()
    else:
        raise ValueError("monte_carlo.parallel must be a boolean or mapping.")

    if scope != "runs":
        raise ValueError("monte_carlo.parallel.scope must be 'runs'.")
    max_cpus = os.cpu_count() or requested_workers
    workers = max(1, min(requested_workers, max_cpus, max(run_count, 1)))
    return {
        "enabled": enabled and workers > 1 and run_count > 1,
        "workers": workers,
        "scope": scope,
    }


def _run_seed(seed: int, run_id: int) -> int:
    return int(seed) + (int(run_id) * 1_000_003)
