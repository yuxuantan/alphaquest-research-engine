from __future__ import annotations

from bisect import bisect_left
import math
from pathlib import Path
import random

import numpy as np
import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.backtest.fills import entry_price, exit_price
from propstack.backtest.metrics import benchmark, calculate_metrics, daily_results
from propstack.backtest.sizing import size_position
from propstack.utils.progress import progress_bar
from propstack.utils.reports import market_timezone, write_report_csv
from propstack.utils.time import parse_time


def run_monkey(
    data: pd.DataFrame,
    base_config: dict,
    monkey_config: dict,
    benchmarks: dict,
    report_dir: str | Path | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Compare one core strategy run against constrained random trades.

    Each monkey iteration creates random entries and random exits directly from
    market bars. The generated path is constrained to stay close to the core
    run's trade count, long/short mix, and average bars in trade.
    """

    seed = int(monkey_config.get("seed", 1))
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)
    constraints = _constraints(monkey_config)

    market = data.sort_values("timestamp").reset_index(drop=True)
    core_result = BacktestEngine(base_config).run(market)
    core_trades = core_result["trades"]
    if core_trades.empty:
        raise ValueError("Core strategy produced no trades; monkey constraints cannot be derived.")

    core_profile = _core_profile(market, core_trades, core_result["metrics"])
    eligible = _eligible_entries(market, base_config, constraints)
    if eligible.empty:
        raise ValueError("No eligible monkey entry bars found for the configured strategy session.")

    rows = []
    total_runs = int(monkey_config.get("runs", 8000))
    threshold = float(monkey_config.get("beat_threshold", constraints.get("beat_threshold", 0.90)))
    valid_position_cache: dict[int, np.ndarray] = {}
    report_paths = _prepare_iteration_report_paths(report_dir)
    report_timezone = market_timezone(base_config)
    progress = progress_bar(total_runs, "monkey runs")

    for run_id in range(1, total_runs + 1):
        trade_count = _sample_trade_count(rng, core_profile["total_trades"], constraints)
        long_trades = _sample_long_count(rng, trade_count, core_profile["long_ratio"], constraints)
        directions = ["long"] * long_trades + ["short"] * (trade_count - long_trades)
        rng.shuffle(directions)

        durations = _sample_durations(np_rng, rng, trade_count, core_profile["average_bars_in_trade"], constraints)
        schedule = _build_schedule(
            np_rng=np_rng,
            eligible=eligible,
            durations=durations,
            directions=directions,
            constraints=constraints,
            max_trades_per_day=int(core_profile["max_trades_per_day"]),
            valid_position_cache=valid_position_cache,
        )
        trades = _build_trade_log(market, schedule, base_config, core_profile)
        metrics = calculate_metrics(
            trades,
            initial_balance=float(base_config.get("core", {}).get("initial_balance", 0)),
        )
        daily = daily_results(trades)
        passed, reason = benchmark(metrics, benchmarks)

        average_bars = float(trades["bars_in_trade"].mean()) if len(trades) else 0.0
        long_ratio = float((trades["direction"] == "long").mean()) if len(trades) else 0.0
        rows.append(
            {
                "run_id": run_id,
                "total_trades": metrics["total_trades"],
                "long_trades": int((trades["direction"] == "long").sum()) if len(trades) else 0,
                "short_trades": int((trades["direction"] == "short").sum()) if len(trades) else 0,
                "long_ratio": long_ratio,
                "average_bars_in_trade": average_bars,
                "trade_count_delta": int(metrics["total_trades"] - core_profile["total_trades"]),
                "long_ratio_delta": float(long_ratio - core_profile["long_ratio"]),
                "average_bars_delta": float(average_bars - core_profile["average_bars_in_trade"]),
                "net_profit": metrics["net_profit"],
                "max_drawdown": metrics["max_drawdown"],
                "max_drawdown_pct": metrics["max_drawdown_pct"],
                "profit_factor": metrics["profit_factor"],
                "expectancy_r": metrics["expectancy_r"],
                "win_rate": metrics["win_rate"],
                "profitable": metrics["net_profit"] > 0,
                "core_net_profit_gt_monkey": core_profile["net_profit"] > metrics["net_profit"],
                "core_max_drawdown_lt_monkey": core_profile["max_drawdown"] < metrics["max_drawdown"],
                "benchmark_passed": passed,
                "failure_reason": reason,
            }
        )
        _append_iteration_report(report_paths, "trades", trades, run_id, report_timezone)
        _append_iteration_report(report_paths, "daily", daily, run_id, report_timezone)
        progress.update(run_id)

    df = pd.DataFrame(rows)
    net_profit_beat_rate = float(df["core_net_profit_gt_monkey"].mean()) if len(df) else 0.0
    drawdown_beat_rate = float(df["core_max_drawdown_lt_monkey"].mean()) if len(df) else 0.0
    passing = int(df["benchmark_passed"].sum()) if len(df) else 0
    profitable = int(df["profitable"].sum()) if len(df) else 0

    summary = {
        "number_of_runs": int(len(df)),
        "core_metrics": {
            "total_trades": int(core_profile["total_trades"]),
            "long_trades": int(core_profile["long_trades"]),
            "short_trades": int(core_profile["short_trades"]),
            "long_ratio": float(core_profile["long_ratio"]),
            "average_bars_in_trade": float(core_profile["average_bars_in_trade"]),
            "net_profit": float(core_profile["net_profit"]),
            "max_drawdown": float(core_profile["max_drawdown"]),
            "max_drawdown_pct": float(core_profile["max_drawdown_pct"]),
        },
        "beat_threshold": threshold,
        "core_beats_monkey_net_profit_rate": net_profit_beat_rate,
        "core_beats_monkey_max_drawdown_rate": drawdown_beat_rate,
        "meets_monkey_goal": net_profit_beat_rate >= threshold and drawdown_beat_rate >= threshold,
        "number_passing_benchmark": passing,
        "percentage_passing_benchmark": float(passing / len(df)) if len(df) else 0.0,
        "profitable_iterations": profitable,
        "percentage_profitable": float(profitable / len(df)) if len(df) else 0.0,
        "median_net_profit": _quantile(df, "net_profit", 0.50),
        "p5_net_profit": _quantile(df, "net_profit", 0.05),
        "p95_net_profit": _quantile(df, "net_profit", 0.95),
        "median_max_drawdown": _quantile(df, "max_drawdown", 0.50),
        "p5_max_drawdown": _quantile(df, "max_drawdown", 0.05),
        "p95_max_drawdown": _quantile(df, "max_drawdown", 0.95),
        "median_average_bars_in_trade": _quantile(df, "average_bars_in_trade", 0.50),
        "median_long_ratio": _quantile(df, "long_ratio", 0.50),
        "constraints": {
            "trade_count_tolerance_pct": float(constraints["trade_count_tolerance_pct"]),
            "trade_count_tolerance": int(constraints["trade_count_tolerance"]),
            "long_short_ratio_tolerance": float(constraints["long_short_ratio_tolerance"]),
            "average_bars_tolerance_pct": float(constraints["average_bars_tolerance_pct"]),
            "duration_shape": float(constraints["duration_shape"]),
            "rth_only": bool(constraints.get("rth_only", True)),
            "enforce_non_overlapping": bool(constraints["enforce_non_overlapping"]),
            "enforce_max_trades_per_day": bool(constraints["enforce_max_trades_per_day"]),
        },
        "iteration_reports_retained": report_paths is not None,
        "iteration_report_files": _iteration_report_files(report_paths),
        "data_subset": monkey_config.get("data_subset", {}),
    }
    return df, summary


def _constraints(monkey_config: dict) -> dict:
    cfg = dict(monkey_config.get("constraints", {}))
    cfg.setdefault("trade_count_tolerance_pct", monkey_config.get("trade_count_tolerance_pct", 0.05))
    cfg.setdefault("trade_count_tolerance", monkey_config.get("trade_count_tolerance", 0))
    cfg.setdefault("long_short_ratio_tolerance", monkey_config.get("long_short_ratio_tolerance", 0.05))
    cfg.setdefault("average_bars_tolerance_pct", monkey_config.get("average_bars_tolerance_pct", 0.10))
    cfg.setdefault("duration_shape", monkey_config.get("duration_shape", 0.70))
    cfg.setdefault("enforce_non_overlapping", monkey_config.get("enforce_non_overlapping", True))
    cfg.setdefault("enforce_max_trades_per_day", monkey_config.get("enforce_max_trades_per_day", False))
    cfg.setdefault("max_schedule_attempts", monkey_config.get("max_schedule_attempts", 100))
    cfg.setdefault("max_entry_attempts_per_trade", monkey_config.get("max_entry_attempts_per_trade", 1500))
    cfg.setdefault("beat_threshold", monkey_config.get("beat_threshold", 0.90))
    return cfg


def _core_profile(data: pd.DataFrame, trades: pd.DataFrame, metrics: dict) -> dict:
    bars = _bars_in_trade(data, trades)
    total = int(len(trades))
    long_trades = int((trades["direction"] == "long").sum())
    short_trades = int((trades["direction"] == "short").sum())
    risk_points = pd.to_numeric(trades.get("risk_points", pd.Series(dtype=float)), errors="coerce")
    max_trades_per_day = int(trades.groupby("session_date")["trade_id"].count().max()) if total else 0
    return {
        "total_trades": total,
        "long_trades": long_trades,
        "short_trades": short_trades,
        "long_ratio": float(long_trades / total) if total else 0.5,
        "average_bars_in_trade": float(bars.mean()) if len(bars) else 1.0,
        "average_risk_points": float(risk_points.dropna().mean()) if risk_points.notna().any() else 1.0,
        "max_trades_per_day": max(max_trades_per_day, 1),
        "net_profit": float(metrics["net_profit"]),
        "max_drawdown": float(metrics["max_drawdown"]),
        "max_drawdown_pct": float(metrics["max_drawdown_pct"]),
    }


def _bars_in_trade(data: pd.DataFrame, trades: pd.DataFrame) -> pd.Series:
    position_by_timestamp = {timestamp: pos for pos, timestamp in enumerate(data["timestamp"])}
    bars = []
    for row in trades.itertuples(index=False):
        entry_pos = position_by_timestamp.get(pd.Timestamp(row.entry_timestamp))
        exit_pos = position_by_timestamp.get(pd.Timestamp(row.exit_timestamp))
        if entry_pos is None or exit_pos is None:
            continue
        bars.append(max(int(exit_pos - entry_pos + 1), 1))
    return pd.Series(bars, dtype=float)


def _eligible_entries(data: pd.DataFrame, base_config: dict, constraints: dict) -> pd.DataFrame:
    strategy = base_config.get("strategy", {})
    entry_params = strategy.get("entry", {}).get("params", {})
    core = base_config.get("core", {})
    start_time = parse_time(entry_params.get("start_time", "00:00:00"))
    end_time = parse_time(entry_params.get("end_time", "23:59:59"))
    flatten_time = parse_time(strategy.get("flatten_time", core.get("flatten_time", "23:59:59")))

    positions = np.arange(len(data), dtype=int)
    exit_limit_by_pos = np.full(len(data), -1, dtype=int)
    for _, group in data.groupby("session_date", sort=False):
        session_positions = group.index.to_numpy(dtype=int)
        exit_positions = [pos for pos in session_positions if data.at[pos, "timestamp"].time() <= flatten_time]
        if not exit_positions:
            continue
        last_exit = int(max(exit_positions))
        exit_limit_by_pos[session_positions] = last_exit

    times = data["timestamp"].dt.time
    mask = (times >= start_time) & (times <= end_time)
    if "is_rth" in data.columns and bool(constraints.get("rth_only", True)):
        mask &= data["is_rth"].fillna(False).astype(bool)
    mask &= exit_limit_by_pos[positions] >= positions

    eligible = pd.DataFrame(
        {
            "position": positions[mask.to_numpy()],
            "session_date": data.loc[mask, "session_date"].to_numpy(),
            "exit_limit": exit_limit_by_pos[mask.to_numpy()],
        }
    )
    return eligible.reset_index(drop=True)


def _sample_trade_count(rng: random.Random, target: int, constraints: dict) -> int:
    tolerance = int(constraints.get("trade_count_tolerance", 0))
    pct_tolerance = int(round(target * float(constraints.get("trade_count_tolerance_pct", 0.05))))
    tolerance = max(tolerance, pct_tolerance)
    lo = max(1, target - tolerance)
    hi = max(lo, target + tolerance)
    return rng.randint(lo, hi)


def _sample_long_count(
    rng: random.Random,
    trade_count: int,
    target_ratio: float,
    constraints: dict,
) -> int:
    tolerance = float(constraints.get("long_short_ratio_tolerance", 0.05))
    lo_ratio = min(max(target_ratio - tolerance, 0.0), 1.0)
    hi_ratio = min(max(target_ratio + tolerance, 0.0), 1.0)
    lo = math.floor(lo_ratio * trade_count)
    hi = math.ceil(hi_ratio * trade_count)
    if 0.0 < target_ratio < 1.0 and trade_count > 1:
        lo = max(1, lo)
        hi = min(trade_count - 1, hi)
    lo = min(max(lo, 0), trade_count)
    hi = min(max(hi, lo), trade_count)
    return rng.randint(lo, hi)


def _sample_durations(
    np_rng: np.random.Generator,
    rng: random.Random,
    trade_count: int,
    target_average: float,
    constraints: dict,
) -> list[int]:
    tolerance = float(constraints.get("average_bars_tolerance_pct", 0.10))
    lo = max(1.0, target_average * (1.0 - tolerance))
    hi = max(lo, target_average * (1.0 + tolerance))
    sampled_average = rng.uniform(lo, hi)
    target_total = max(trade_count, int(round(sampled_average * trade_count)))
    remaining = target_total - trade_count
    if remaining <= 0:
        return [1] * trade_count

    shape = max(float(constraints.get("duration_shape", 0.70)), 0.05)
    weights = np_rng.gamma(shape=shape, scale=1.0, size=trade_count)
    if float(weights.sum()) <= 0:
        weights = np.ones(trade_count)
    extra = np_rng.multinomial(remaining, weights / weights.sum())
    return [int(x) for x in (extra + 1)]


def _build_schedule(
    np_rng: np.random.Generator,
    eligible: pd.DataFrame,
    durations: list[int],
    directions: list[str],
    constraints: dict,
    max_trades_per_day: int,
    valid_position_cache: dict[int, np.ndarray],
) -> list[dict]:
    positions = eligible["position"].to_numpy(dtype=int)
    rooms = eligible["exit_limit"].to_numpy(dtype=int) - positions + 1
    session_dates = pd.Series(eligible["session_date"].to_numpy(), index=positions).to_dict()
    enforce_non_overlapping = bool(constraints.get("enforce_non_overlapping", True))
    enforce_daily_cap = bool(constraints.get("enforce_max_trades_per_day", False))
    max_schedule_attempts = int(constraints.get("max_schedule_attempts", 100))

    order = list(range(len(durations)))
    for _ in range(max_schedule_attempts):
        order.sort(key=lambda idx: (durations[idx], np_rng.random()), reverse=True)
        starts: list[int] = []
        ends: list[int] = []
        day_counts: dict[object, int] = {}
        schedule: list[dict | None] = [None] * len(durations)

        for idx in order:
            placement = _place_trade(
                np_rng=np_rng,
                positions=positions,
                session_dates=session_dates,
                rooms=rooms,
                starts=starts,
                ends=ends,
                day_counts=day_counts,
                duration=durations[idx],
                direction=directions[idx],
                enforce_non_overlapping=enforce_non_overlapping,
                enforce_daily_cap=enforce_daily_cap,
                max_trades_per_day=max_trades_per_day,
                max_attempts=int(constraints.get("max_entry_attempts_per_trade", 1500)),
                valid_position_cache=valid_position_cache,
            )
            if placement is None:
                break
            schedule[idx] = placement
        else:
            return sorted([item for item in schedule if item is not None], key=lambda item: item["entry_pos"])

    raise RuntimeError(
        "Unable to place constrained monkey trades. "
        "Relax trade_count, average_bars, or non-overlap constraints."
    )


def _place_trade(
    np_rng: np.random.Generator,
    positions: np.ndarray,
    session_dates: dict,
    rooms: np.ndarray,
    starts: list[int],
    ends: list[int],
    day_counts: dict[object, int],
    duration: int,
    direction: str,
    enforce_non_overlapping: bool,
    enforce_daily_cap: bool,
    max_trades_per_day: int,
    max_attempts: int,
    valid_position_cache: dict[int, np.ndarray],
) -> dict | None:
    valid_positions = valid_position_cache.get(duration)
    if valid_positions is None:
        valid_positions = positions[rooms >= duration]
        valid_position_cache[duration] = valid_positions
    if len(valid_positions) == 0:
        return None

    attempts = min(max_attempts, len(valid_positions))
    if attempts == len(valid_positions):
        candidates = np_rng.permutation(valid_positions)
    else:
        candidates = np_rng.choice(valid_positions, size=attempts, replace=False)

    for candidate in candidates:
        entry_pos = int(candidate)
        exit_pos = entry_pos + duration - 1
        day = session_dates[entry_pos]
        if enforce_daily_cap and day_counts.get(day, 0) >= max_trades_per_day:
            continue
        if enforce_non_overlapping and _has_overlap(starts, ends, entry_pos, exit_pos):
            continue

        if enforce_non_overlapping:
            insert_at = bisect_left(starts, entry_pos)
            starts.insert(insert_at, entry_pos)
            ends.insert(insert_at, exit_pos)
        day_counts[day] = day_counts.get(day, 0) + 1
        return {
            "entry_pos": entry_pos,
            "exit_pos": exit_pos,
            "duration": duration,
            "direction": direction,
        }
    return None


def _has_overlap(starts: list[int], ends: list[int], start: int, end: int) -> bool:
    idx = bisect_left(starts, start)
    if idx > 0 and ends[idx - 1] >= start:
        return True
    return idx < len(starts) and starts[idx] <= end


def _build_trade_log(
    data: pd.DataFrame,
    schedule: list[dict],
    base_config: dict,
    core_profile: dict,
) -> pd.DataFrame:
    core = base_config.get("core", {})
    tick_size = float(core.get("tick_size", 0.25))
    tick_value = float(core.get("tick_value", 12.5))
    commission = float(core.get("commission_per_contract", 2.5))
    slippage_ticks = float(core.get("slippage_ticks", 1))
    risk_points = max(float(core_profile.get("average_risk_points", tick_size)), tick_size)

    rows = []
    for trade_id, item in enumerate(schedule, start=1):
        entry_bar = data.iloc[item["entry_pos"]]
        exit_bar = data.iloc[item["exit_pos"]]
        direction = item["direction"]
        ep = entry_price(float(entry_bar["open"]), direction, tick_size, slippage_ticks)
        xp = exit_price(float(exit_bar["close"]), direction, tick_size, slippage_ticks)
        point_pnl = xp - ep if direction == "long" else ep - xp
        sizing = size_position(core, risk_points, tick_size, tick_value)
        if sizing.contracts < 1:
            continue
        contracts = sizing.contracts
        gross = point_pnl / tick_size * tick_value * contracts
        total_commission = commission * contracts * 2
        slippage_cost = slippage_ticks * tick_value * contracts * 2
        net = gross - total_commission
        path = data.iloc[item["entry_pos"] : item["exit_pos"] + 1]
        if direction == "long":
            mfe = max(0.0, float(path["high"].max()) - ep)
            mae = max(0.0, ep - float(path["low"].min()))
        else:
            mfe = max(0.0, ep - float(path["low"].min()))
            mae = max(0.0, float(path["high"].max()) - ep)
        rows.append(
            {
                "trade_id": trade_id,
                "strategy_name": "monkey_random",
                "session_date": entry_bar["session_date"],
                "direction": direction,
                "level_type": "random",
                "swept_level": pd.NA,
                "sweep_timestamp": pd.NaT,
                "sweep_high": pd.NA,
                "sweep_low": pd.NA,
                "reclaim_timestamp": pd.NaT,
                "entry_timestamp": entry_bar["timestamp"],
                "entry_price": ep,
                "stop_price": pd.NA,
                "target_price": pd.NA,
                "risk_points": risk_points,
                "contracts": contracts,
                **sizing.report_fields(),
                "max_favorable_excursion": mfe,
                "max_adverse_excursion": mae,
                "exit_timestamp": exit_bar["timestamp"],
                "exit_price": xp,
                "exit_reason": "random_exit",
                "bars_in_trade": int(item["duration"]),
                "gross_pnl": gross,
                "net_pnl": net,
                "r_multiple": point_pnl / risk_points if risk_points else 0.0,
                "commission": total_commission,
                "slippage_cost": slippage_cost,
            }
        )
    return pd.DataFrame(rows)


def _prepare_iteration_report_paths(report_dir: str | Path | None) -> dict[str, Path] | None:
    if report_dir is None:
        return None
    root = Path(report_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "trades": root / "monkey_iteration_trades.csv",
        "daily": root / "monkey_iteration_daily.csv",
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
    timezone: str | None = None,
) -> None:
    if paths is None or frame.empty:
        return
    out = frame.copy()
    out.insert(0, "run_id", run_id)
    path = paths[name]
    write_report_csv(out, path, timezone, mode="a", header=not path.exists(), index=False)


def _iteration_report_files(paths: dict[str, Path] | None) -> list[str]:
    if paths is None:
        return []
    return [str(path) for path in paths.values()]


def _quantile(df: pd.DataFrame, column: str, value: float) -> float:
    if df.empty or column not in df:
        return 0.0
    result = float(df[column].quantile(value))
    return result if math.isfinite(result) else 0.0
