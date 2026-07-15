from __future__ import annotations

import math
import pandas as pd


def _ordered_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty or "exit_timestamp" not in trades.columns:
        return trades
    out = trades.copy()
    out["_exit_timestamp_order"] = pd.to_datetime(out["exit_timestamp"], utc=True)
    sort_columns = ["_exit_timestamp_order"]
    if "trade_id" in out.columns:
        sort_columns.append("trade_id")
    return out.sort_values(sort_columns, kind="mergesort").drop(columns=["_exit_timestamp_order"])


def equity_curve(trades: pd.DataFrame, initial_balance: float = 0.0) -> pd.Series:
    if trades.empty:
        return pd.Series(dtype=float)
    ordered = _ordered_trades(trades)
    cumulative = initial_balance + ordered["net_pnl"].cumsum()
    return pd.concat([pd.Series([initial_balance]), cumulative], ignore_index=True)


def drawdown_stats(trades: pd.DataFrame, initial_balance: float = 0.0) -> tuple[float, float]:
    eq = equity_curve(trades, initial_balance=initial_balance)
    if eq.empty:
        return 0.0, 0.0
    peaks = eq.cummax()
    dd_amount = peaks - eq
    valid_peaks = peaks[peaks > 0]
    if valid_peaks.empty:
        return float(dd_amount.max()), 0.0
    dd_pct = (dd_amount.loc[valid_peaks.index] / valid_peaks).max()
    return float(dd_amount.max()), float(dd_pct)


def max_drawdown(trades: pd.DataFrame, initial_balance: float = 0.0) -> float:
    drawdown, _ = drawdown_stats(trades, initial_balance=initial_balance)
    return drawdown


def max_consecutive_losses(trades: pd.DataFrame) -> int:
    best = cur = 0
    for pnl in trades.get("net_pnl", []):
        if pnl < 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return int(best)


def daily_results(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["session_date", "net_pnl", "trades", "wins", "losses"])
    g = trades.groupby("session_date")
    out = g.agg(
        net_pnl=("net_pnl", "sum"),
        gross_pnl=("gross_pnl", "sum"),
        trades=("trade_id", "count"),
        wins=("net_pnl", lambda s: int((s > 0).sum())),
        losses=("net_pnl", lambda s: int((s < 0).sum())),
    ).reset_index()
    return out


def _elapsed_years(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    timestamps = pd.to_datetime(
        pd.concat([trades["entry_timestamp"], trades["exit_timestamp"]]), utc=True
    )
    elapsed_days = max((timestamps.max() - timestamps.min()).total_seconds() / 86400.0, 1.0)
    return elapsed_days / 365.25


def calculate_metrics(trades: pd.DataFrame, initial_balance: float = 0.0) -> dict:
    if trades.empty:
        return {
            "total_trades": 0,
            "trades_per_year": 0.0,
            "net_profit": 0.0,
            "profit_factor": 0.0,
            "expectancy_r": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
            "cagr": 0.0,
            "mar": 0.0,
            "worst_day": 0.0,
            "best_day": 0.0,
            "best_day_concentration": 0.0,
            "max_consecutive_losses": 0,
            "positive_month_rate": 0.0,
            "win_rate": 0.0,
            "apex_rule_violations": 0,
            "apex_forced_flatten_trades": 0,
        }
    trades = _ordered_trades(trades)
    wins = trades.loc[trades["net_pnl"] > 0, "net_pnl"].sum()
    losses = abs(trades.loc[trades["net_pnl"] < 0, "net_pnl"].sum())
    pf = float(wins / losses) if losses else math.inf
    daily = daily_results(trades)
    exit_ts = pd.to_datetime(trades["exit_timestamp"], utc=True).dt.tz_convert(None)
    months = trades.assign(month=exit_ts.dt.to_period("M"))
    monthly = months.groupby("month")["net_pnl"].sum()
    net_profit = float(trades["net_pnl"].sum())
    best_day = float(daily["net_pnl"].max()) if len(daily) else 0.0
    years = _elapsed_years(trades)
    drawdown, max_drawdown_pct = drawdown_stats(trades, initial_balance=initial_balance)
    ending_balance = initial_balance + net_profit
    if initial_balance <= 0 or years <= 0:
        cagr = 0.0
    elif ending_balance > 0:
        cagr = (ending_balance / initial_balance) ** (1 / years) - 1
    else:
        cagr = -1.0
    mar = cagr / max_drawdown_pct if max_drawdown_pct > 0 else (math.inf if cagr > 0 else 0.0)
    return {
        "total_trades": int(len(trades)),
        "trades_per_year": float(len(trades) / years) if years > 0 else 0.0,
        "net_profit": net_profit,
        "profit_factor": pf,
        "expectancy_r": float(trades["r_multiple"].mean()),
        "max_drawdown": drawdown,
        "max_drawdown_pct": max_drawdown_pct,
        "cagr": cagr,
        "mar": mar,
        "worst_day": float(daily["net_pnl"].min()) if len(daily) else 0.0,
        "best_day": best_day,
        "best_day_concentration": float(best_day / net_profit) if net_profit > 0 else 0.0,
        "max_consecutive_losses": max_consecutive_losses(trades),
        "positive_month_rate": float((monthly > 0).mean()) if len(monthly) else 0.0,
        "win_rate": float((trades["net_pnl"] > 0).mean()),
        "average_trade": float(trades["net_pnl"].mean()),
        "apex_rule_violations": _boolean_count(trades, "apex_rule_violation"),
        "apex_forced_flatten_trades": _boolean_count(trades, "was_forced_flatten"),
    }


def benchmark(metrics: dict, thresholds: dict) -> tuple[bool, str]:
    checks = [
        ("apex_rule_violations", metrics.get("apex_rule_violations", 0) <= 0),
        ("min_total_net_profit", metrics.get("net_profit", 0) >= thresholds.get("min_total_net_profit", float("-inf"))),
        ("min_profit_factor", metrics.get("profit_factor", 0) >= thresholds.get("min_profit_factor", 0)),
        ("min_expectancy_r", metrics.get("expectancy_r", 0) >= thresholds.get("min_expectancy_r", float("-inf"))),
        ("max_drawdown", metrics.get("max_drawdown", 0) <= thresholds.get("max_drawdown", float("inf"))),
        ("max_drawdown_pct", metrics.get("max_drawdown_pct", 0) <= thresholds.get("max_drawdown_pct", float("inf"))),
        ("min_cagr", metrics.get("cagr", 0) >= thresholds.get("min_cagr", float("-inf"))),
        ("min_mar", metrics.get("mar", 0) >= thresholds.get("min_mar", float("-inf"))),
        ("min_win_rate", metrics.get("win_rate", 0) >= thresholds.get("min_win_rate", 0)),
        ("min_trades_per_year", metrics.get("trades_per_year", 0) >= thresholds.get("min_trades_per_year", 0)),
        ("max_consecutive_losses", metrics.get("max_consecutive_losses", 0) <= thresholds.get("max_consecutive_losses", 10**9)),
        ("min_trade_count", metrics.get("total_trades", 0) >= thresholds.get("min_trade_count", 0)),
        ("preferred_min_total_trades", metrics.get("total_trades", 0) >= thresholds.get("preferred_min_total_trades", 0)),
        ("max_best_day_concentration", metrics.get("best_day_concentration", 0) <= thresholds.get("max_best_day_concentration", 1)),
        ("min_positive_month_rate", metrics.get("positive_month_rate", 0) >= thresholds.get("min_positive_month_rate", 0)),
    ]
    failures = [name for name, ok in checks if not ok]
    return not failures, ";".join(failures)


def _boolean_count(frame: pd.DataFrame, column: str) -> int:
    if column not in frame.columns:
        return 0
    return int(frame[column].fillna(False).astype(bool).sum())
