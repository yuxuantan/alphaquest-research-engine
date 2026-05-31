from __future__ import annotations

import random
import pandas as pd

from propstack.prop.rules import PropRules
from propstack.prop.simulator import simulate_prop_path
from propstack.utils.progress import progress_bar


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
    rng = random.Random(cfg.get("seed", 1))
    rows = []
    total_runs = int(cfg.get("runs", 1000))
    progress = progress_bar(total_runs, "monte carlo runs")
    for run_id in range(1, total_runs + 1):
        path = _path_sample(trades, rng, cfg)
        rows.append({"run_id": run_id, **simulate_prop_path(path, rules)})
        progress.update(run_id)
    df = pd.DataFrame(rows)
    summary = {
        "number_of_runs": int(len(df)),
        "median_ending_balance": float(df["ending_balance"].median()) if len(df) else rules.starting_balance,
        "p5_ending_balance": float(df["ending_balance"].quantile(0.05)) if len(df) else rules.starting_balance,
        "p95_drawdown": float(df["max_drawdown"].quantile(0.95)) if len(df) else 0.0,
        "probability_account_breach": float(df["account_breached"].mean()) if len(df) else 0.0,
        "probability_payout_eligible": float(df["payout_eligible"].mean()) if len(df) else 0.0,
        "probability_profit_before_drawdown": float(df["profit_before_drawdown"].mean()) if len(df) else 0.0,
        "probability_net_profit_gt_0": float((df["net_pnl"] > 0).mean()) if len(df) else 0.0,
    }
    summary["meets_prop_pass_chance_benchmark"] = (
        summary["probability_profit_before_drawdown"]
        >= float(cfg.get("min_monte_carlo_prop_pass_chance", 0.0))
    )
    return df, summary
