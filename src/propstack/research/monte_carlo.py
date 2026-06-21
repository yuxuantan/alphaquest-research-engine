from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
import math
import os
import random
import pandas as pd

from propstack.prop.rules import PropRules
from propstack.prop.simulator import simulate_prop_path, simulate_prop_path_with_events
from propstack.utils.progress import progress_bar

_WORKER_TRADES = None
_WORKER_CFG = None
_WORKER_RULES = None

_PATH_TRADE_AUDIT_COLUMNS = [
    "run_id",
    "sample_index",
    "path_index",
    "source_trade_id",
    "source_session_date",
    "source_contracts",
    "sim_contracts",
    "source_net_pnl",
    "sim_net_pnl",
    "position_sizing_mode",
    "position_sizing_net_liq",
    "target_risk_amount",
    "dollar_risk_per_contract",
    "unrounded_contracts",
    "planned_dollar_risk",
    "was_skipped",
    "skip_reason",
    "was_loss_clustered",
    "was_applied",
    "account_number",
    "account_phase",
    "balance",
    "account_high",
    "trailing_floor",
    "event",
    "breach_reason",
    "trader_net_pnl",
    "total_challenge_fees",
    "gross_payouts",
    "net_payouts",
    "total_payout_count",
    "account_payout_count",
    "funded_profit_days",
    "challenge_total_profit",
    "challenge_largest_trade_profit",
    "challenge_consistency_ratio",
]

_PATH_EVENT_AUDIT_COLUMNS = [
    "run_id",
    "event_sequence",
    "path_index",
    "source_trade_id",
    "source_session_date",
    "source_contracts",
    "sim_contracts",
    "source_net_pnl",
    "sim_net_pnl",
    "position_sizing_mode",
    "position_sizing_net_liq",
    "target_risk_amount",
    "dollar_risk_per_contract",
    "unrounded_contracts",
    "planned_dollar_risk",
    "balance",
    "account_high",
    "trailing_floor",
    "max_drawdown",
    "drawdown_limit_balance",
    "payout_target_balance",
    "profit_target_balance",
    "event",
    "breach_reason",
    "daily_pnl",
    "account_number",
    "account_phase",
    "trader_net_pnl",
    "total_challenge_fees",
    "gross_payouts",
    "net_payouts",
    "total_payout_count",
    "account_payout_count",
    "funded_profit_days",
    "challenge_total_profit",
    "challenge_largest_trade_profit",
    "challenge_consistency_ratio",
    "payout_request",
    "payout_net",
    "account_breached",
]


def _path_sample(trades: pd.DataFrame, rng: random.Random, cfg: dict) -> pd.DataFrame:
    path, _ = _sample_path_with_audit(trades, rng, cfg, collect_audit=False)
    return path


def _sample_path_with_audit(
    trades: pd.DataFrame,
    rng: random.Random,
    cfg: dict,
    collect_audit: bool,
) -> tuple[pd.DataFrame, list[dict]]:
    if trades.empty:
        return trades, []

    source = trades.copy().reset_index(drop=True)
    source["_source_row"] = source.index + 1
    source["_source_trade_id"] = source["trade_id"] if "trade_id" in source.columns else source["_source_row"]
    source["_source_net_pnl"] = source["net_pnl"]

    out = source.sample(frac=1, random_state=rng.randint(1, 10**9)).reset_index(drop=True)
    out["_sample_index"] = out.index + 1

    audit_rows = []
    kept_source_rows = set()
    keep = []
    for _, row in out.iterrows():
        skip_reason = ""
        if rng.random() < cfg.get("skip_trade_probability", 0.0):
            skip_reason = "skip_trade_probability"
            keep.append(False)
        elif row["net_pnl"] > 0 and rng.random() < cfg.get("skip_winning_trade_probability", 0.0):
            skip_reason = "skip_winning_trade_probability"
            keep.append(False)
        else:
            keep.append(True)
            kept_source_rows.add(int(row["_source_row"]))
        if collect_audit:
            audit_rows.append(_path_trade_audit_row(row, was_skipped=bool(skip_reason), skip_reason=skip_reason))

    out = out.loc[keep].copy().reset_index(drop=True)
    cluster_losses = bool(cfg.get("cluster_losses", False))
    if cluster_losses and not out.empty:
        out = pd.concat([out[out["net_pnl"] < 0], out[out["net_pnl"] >= 0]], ignore_index=True)
    if not out.empty:
        out["_path_index"] = out.index + 1

    if collect_audit:
        path_lookup = {
            int(row["_source_row"]): {
                "path_index": int(row["_path_index"]),
                "was_loss_clustered": bool(cluster_losses and float(row["_source_net_pnl"]) < 0),
            }
            for _, row in out.iterrows()
        }
        for audit_row in audit_rows:
            lookup = path_lookup.get(int(audit_row["_source_row"]))
            audit_row.pop("_source_row", None)
            if lookup:
                audit_row.update(lookup)
            else:
                audit_row.update({"path_index": None, "was_loss_clustered": False})
    return out, audit_rows


def run_monte_carlo(trades: pd.DataFrame, cfg: dict, rules: PropRules) -> tuple[pd.DataFrame, dict]:
    results, summary, _, _ = _run_monte_carlo(trades, cfg, rules, False, False)
    return results, summary


def run_monte_carlo_with_audit(
    trades: pd.DataFrame,
    cfg: dict,
    rules: PropRules,
) -> tuple[pd.DataFrame, dict, pd.DataFrame, pd.DataFrame]:
    return _run_monte_carlo(
        trades,
        cfg,
        rules,
        bool(cfg.get("retain_path_trades", False)),
        bool(cfg.get("retain_path_events", False)),
    )


def _run_monte_carlo(
    trades: pd.DataFrame,
    cfg: dict,
    rules: PropRules,
    retain_path_trades: bool,
    retain_path_events: bool,
) -> tuple[pd.DataFrame, dict, pd.DataFrame, pd.DataFrame]:
    total_runs = int(cfg.get("runs", 1000))
    parallel = _parallel_settings(cfg, total_runs)
    audit_enabled = retain_path_trades or retain_path_events
    path_trade_rows = []
    path_event_rows = []
    if parallel["enabled"]:
        if audit_enabled:
            rows, path_trade_rows, path_event_rows = _run_parallel_monte_carlo_with_audit(
                trades,
                cfg,
                rules,
                total_runs,
                parallel["workers"],
                retain_path_trades,
                retain_path_events,
            )
        else:
            rows = _run_parallel_monte_carlo(trades, cfg, rules, total_runs, parallel["workers"])
    else:
        rows = []
        progress = progress_bar(total_runs, "monte carlo runs")
        for run_id in range(1, total_runs + 1):
            if audit_enabled:
                row, trade_rows, event_rows = _evaluate_monte_carlo_run_with_audit(
                    run_id,
                    trades,
                    cfg,
                    rules,
                    retain_path_trades,
                    retain_path_events,
                )
                rows.append(row)
                path_trade_rows.extend(trade_rows)
                path_event_rows.extend(event_rows)
            else:
                rows.append(_evaluate_monte_carlo_run(run_id, trades, cfg, rules))
            progress.update(run_id)
    df = pd.DataFrame(rows).sort_values("run_id").reset_index(drop=True)
    summary = {
        "number_of_runs": int(len(df)),
        "median_ending_balance": float(df["ending_balance"].median()) if len(df) else rules.starting_balance,
        "p5_ending_balance": float(df["ending_balance"].quantile(0.05)) if len(df) else rules.starting_balance,
        "mean_net_pnl": float(df["net_pnl"].mean()) if len(df) else 0.0,
        "average_net_pnl": float(df["net_pnl"].mean()) if len(df) else 0.0,
        "median_net_pnl": float(df["net_pnl"].median()) if len(df) else 0.0,
        "p5_net_pnl": float(df["net_pnl"].quantile(0.05)) if len(df) else 0.0,
        "p95_net_pnl": float(df["net_pnl"].quantile(0.95)) if len(df) else 0.0,
        "p95_drawdown": float(df["max_drawdown"].quantile(0.95)) if len(df) else 0.0,
        "probability_account_breach": float(df["account_breached"].mean()) if len(df) else 0.0,
        "probability_payout_eligible": float(df["payout_eligible"].mean()) if len(df) else 0.0,
        "probability_profit_before_drawdown": float(df["profit_before_drawdown"].mean()) if len(df) else 0.0,
        "probability_net_profit_gt_0": float((df["net_pnl"] > 0).mean()) if len(df) else 0.0,
        "sampling": {
            "seed": int(cfg.get("seed", 1)),
            "skip_trade_probability": float(cfg.get("skip_trade_probability", 0.0)),
            "skip_winning_trade_probability": float(cfg.get("skip_winning_trade_probability", 0.0)),
            "cluster_losses": bool(cfg.get("cluster_losses", False)),
        },
        "parallel": {
            "enabled": parallel["enabled"],
            "workers": parallel["workers"] if parallel["enabled"] else 1,
            "scope": "runs",
        },
    }
    if "challenge_passes" in df.columns:
        summary.update(
            {
                "probability_challenge_passed": float((df["challenge_passes"] > 0).mean()) if len(df) else 0.0,
                "probability_funded_payout": float((df["payout_count"] > 0).mean()) if len(df) else 0.0,
                "probability_account_terminated_after_payouts": (
                    float((df["accounts_terminated"] > 0).mean()) if len(df) else 0.0
                ),
                "median_accounts_purchased": float(df["accounts_purchased"].median()) if len(df) else 0.0,
                "median_accounts_breached": float(df["accounts_breached"].median()) if len(df) else 0.0,
                "median_challenge_passes": float(df["challenge_passes"].median()) if len(df) else 0.0,
                "median_payout_count": float(df["payout_count"].median()) if len(df) else 0.0,
                "median_total_challenge_fees": float(df["total_challenge_fees"].median()) if len(df) else 0.0,
                "median_net_payouts": float(df["net_payouts"].median()) if len(df) else 0.0,
            }
        )
    benchmark_metric = str(
        cfg.get(
            "monte_carlo_prop_benchmark_metric",
            "mean_net_pnl"
            if bool(getattr(rules, "account_lifecycle_enabled", False))
            else "probability_profit_before_drawdown",
        )
    )
    mean_pnl_metrics = {"mean_net_pnl", "average_net_pnl"}
    benchmark_threshold = (
        float(cfg.get("min_monte_carlo_mean_net_pnl", 0.0))
        if benchmark_metric in mean_pnl_metrics
        else float(cfg.get("min_monte_carlo_prop_pass_chance", 0.0))
    )
    summary["prop_pass_chance_benchmark_metric"] = benchmark_metric
    summary["prop_pass_chance_benchmark_threshold"] = benchmark_threshold
    benchmark_value = float(summary.get(benchmark_metric, 0.0))
    summary["meets_prop_pass_chance_benchmark"] = (
        benchmark_value > benchmark_threshold
        if benchmark_metric in mean_pnl_metrics
        else benchmark_value >= benchmark_threshold
    )
    path_trades = pd.DataFrame(path_trade_rows, columns=_PATH_TRADE_AUDIT_COLUMNS)
    path_events = pd.DataFrame(path_event_rows, columns=_PATH_EVENT_AUDIT_COLUMNS)
    if len(path_trades):
        path_trades = path_trades.sort_values(["run_id", "sample_index"]).reset_index(drop=True)
    if len(path_events):
        if "event_sequence" in path_events.columns and not path_events["event_sequence"].isna().all():
            path_events = path_events.sort_values(["run_id", "event_sequence"]).reset_index(drop=True)
        else:
            path_events = path_events.sort_values(["run_id", "path_index"], na_position="last").reset_index(drop=True)
    return df, summary, path_trades, path_events


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
        futures = {
            executor.submit(_run_monte_carlo_batch_worker, batch): len(batch)
            for batch in _run_id_batches(total_runs, workers)
        }
        completed = 0
        for future in as_completed(futures):
            rows.extend(future.result())
            completed += futures[future]
            progress.update(completed)
    return rows


def _run_parallel_monte_carlo_with_audit(
    trades: pd.DataFrame,
    cfg: dict,
    rules: PropRules,
    total_runs: int,
    workers: int,
    retain_path_trades: bool,
    retain_path_events: bool,
) -> tuple[list[dict], list[dict], list[dict]]:
    rows = []
    path_trade_rows = []
    path_event_rows = []
    progress = progress_bar(total_runs, "monte carlo runs")
    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_monte_carlo_worker,
        initargs=(trades, cfg, rules),
    ) as executor:
        futures = {
            executor.submit(
                _run_audited_monte_carlo_batch_worker,
                batch,
                retain_path_trades,
                retain_path_events,
            ): len(batch)
            for batch in _run_id_batches(total_runs, workers)
        }
        completed = 0
        for future in as_completed(futures):
            batch_rows, trade_rows, event_rows = future.result()
            rows.extend(batch_rows)
            path_trade_rows.extend(trade_rows)
            path_event_rows.extend(event_rows)
            completed += futures[future]
            progress.update(completed)
    return rows, path_trade_rows, path_event_rows


def _init_monte_carlo_worker(trades: pd.DataFrame, cfg: dict, rules: PropRules) -> None:
    global _WORKER_TRADES, _WORKER_CFG, _WORKER_RULES
    _WORKER_TRADES = trades
    _WORKER_CFG = cfg
    _WORKER_RULES = rules


def _run_monte_carlo_worker(run_id: int) -> dict:
    if _WORKER_TRADES is None or _WORKER_CFG is None or _WORKER_RULES is None:
        raise RuntimeError("Monte Carlo worker was not initialized.")
    return _evaluate_monte_carlo_run(run_id, _WORKER_TRADES, _WORKER_CFG, _WORKER_RULES)


def _run_monte_carlo_batch_worker(run_ids: list[int]) -> list[dict]:
    return [_run_monte_carlo_worker(run_id) for run_id in run_ids]


def _run_audited_monte_carlo_worker(
    run_id: int,
    retain_path_trades: bool,
    retain_path_events: bool,
) -> tuple[dict, list[dict], list[dict]]:
    if _WORKER_TRADES is None or _WORKER_CFG is None or _WORKER_RULES is None:
        raise RuntimeError("Monte Carlo worker was not initialized.")
    return _evaluate_monte_carlo_run_with_audit(
        run_id,
        _WORKER_TRADES,
        _WORKER_CFG,
        _WORKER_RULES,
        retain_path_trades,
        retain_path_events,
    )


def _run_audited_monte_carlo_batch_worker(
    run_ids: list[int],
    retain_path_trades: bool,
    retain_path_events: bool,
) -> tuple[list[dict], list[dict], list[dict]]:
    rows = []
    path_trade_rows = []
    path_event_rows = []
    for run_id in run_ids:
        row, trade_rows, event_rows = _run_audited_monte_carlo_worker(
            run_id,
            retain_path_trades,
            retain_path_events,
        )
        rows.append(row)
        path_trade_rows.extend(trade_rows)
        path_event_rows.extend(event_rows)
    return rows, path_trade_rows, path_event_rows


def _evaluate_monte_carlo_run(run_id: int, trades: pd.DataFrame, cfg: dict, rules: PropRules) -> dict:
    rng = random.Random(_run_seed(int(cfg.get("seed", 1)), run_id))
    path = _path_sample(trades, rng, cfg)
    return {"run_id": run_id, **simulate_prop_path(path, rules, _path_sizing_config(cfg))}


def _evaluate_monte_carlo_run_with_audit(
    run_id: int,
    trades: pd.DataFrame,
    cfg: dict,
    rules: PropRules,
    retain_path_trades: bool,
    retain_path_events: bool,
) -> tuple[dict, list[dict], list[dict]]:
    rng = random.Random(_run_seed(int(cfg.get("seed", 1)), run_id))
    path, path_trade_rows = _sample_path_with_audit(trades, rng, cfg, retain_path_trades)
    if retain_path_events or retain_path_trades:
        result, simulation_event_rows = simulate_prop_path_with_events(path, rules, _path_sizing_config(cfg))
        _apply_simulation_events_to_path_trades(path_trade_rows, simulation_event_rows)
        path_event_rows = simulation_event_rows if retain_path_events else []
    else:
        result = simulate_prop_path(path, rules, _path_sizing_config(cfg))
        path_event_rows = []

    for row in path_trade_rows:
        row["run_id"] = run_id
    for row in path_event_rows:
        row["run_id"] = run_id
    return {"run_id": run_id, **result}, path_trade_rows, path_event_rows


def _path_trade_audit_row(row, was_skipped: bool, skip_reason: str) -> dict:
    return {
        "run_id": None,
        "sample_index": int(row["_sample_index"]),
        "path_index": None,
        "source_trade_id": _scalar(row["_source_trade_id"]),
        "source_session_date": _scalar(row.get("session_date")),
        "source_contracts": int(row.get("contracts", 1)),
        "sim_contracts": None,
        "source_net_pnl": float(row["_source_net_pnl"]),
        "sim_net_pnl": None,
        "position_sizing_mode": _scalar(row.get("position_sizing_mode")),
        "position_sizing_net_liq": None,
        "target_risk_amount": None,
        "dollar_risk_per_contract": _scalar(row.get("dollar_risk_per_contract")),
        "unrounded_contracts": None,
        "planned_dollar_risk": None,
        "was_skipped": was_skipped,
        "skip_reason": skip_reason,
        "was_loss_clustered": False,
        "was_applied": False,
        "_source_row": int(row["_source_row"]),
    }


def _scalar(value):
    if hasattr(value, "item"):
        value = value.item()
    if pd.isna(value):
        return None
    return value


def _apply_simulation_events_to_path_trades(path_trade_rows: list[dict], event_rows: list[dict]) -> None:
    event_by_path_index = {}
    for row in event_rows:
        path_index = row.get("path_index")
        if path_index is None or pd.isna(path_index):
            continue
        key = int(path_index)
        event_name = str(row.get("event", ""))
        if key not in event_by_path_index or event_name.startswith("trade"):
            event_by_path_index[key] = row
    for row in path_trade_rows:
        path_index = row.get("path_index")
        if path_index is None or pd.isna(path_index):
            continue
        event = event_by_path_index.get(int(path_index))
        if not event:
            continue
        for key in [
            "sim_contracts",
            "sim_net_pnl",
            "position_sizing_mode",
            "position_sizing_net_liq",
            "target_risk_amount",
            "dollar_risk_per_contract",
            "unrounded_contracts",
            "planned_dollar_risk",
            "account_number",
            "account_phase",
            "balance",
            "account_high",
            "trailing_floor",
            "event",
            "breach_reason",
            "trader_net_pnl",
            "total_challenge_fees",
            "gross_payouts",
            "net_payouts",
            "total_payout_count",
            "account_payout_count",
            "funded_profit_days",
            "challenge_total_profit",
            "challenge_largest_trade_profit",
            "challenge_consistency_ratio",
        ]:
            row[key] = event.get(key)
        row["was_applied"] = "trade" in str(event.get("event", "")).split("|")
        if event.get("event") == "position_size_skip":
            row["was_skipped"] = True
            row["skip_reason"] = "position_sizing_min_contracts"


def _path_sizing_config(cfg: dict) -> dict:
    return {
        "core": cfg.get("_core") or {},
        "position_sizing": cfg.get("position_sizing") or {"mode": "reference"},
        "adverse_slippage_per_trade": float(cfg.get("adverse_slippage_per_trade", 0.0)),
    }


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


def _run_id_batches(total_runs: int, workers: int) -> list[list[int]]:
    run_ids = list(range(1, int(total_runs) + 1))
    if not run_ids:
        return []
    chunk_size = _parallel_chunk_size(len(run_ids), workers)
    return [run_ids[start : start + chunk_size] for start in range(0, len(run_ids), chunk_size)]


def _parallel_chunk_size(item_count: int, workers: int) -> int:
    if item_count <= 0:
        return 1
    target_chunks = max(1, int(workers) * 4)
    return max(1, min(128, math.ceil(item_count / target_chunks)))


def _run_seed(seed: int, run_id: int) -> int:
    return int(seed) + (int(run_id) * 1_000_003)
