from __future__ import annotations

import math
from typing import Any

import pandas as pd

from propstack.utils.hashing import object_sha256


TRADE_SIGNATURE_COLUMNS = (
    "entry_timestamp",
    "exit_timestamp",
    "direction",
    "entry_price",
    "stop_price",
    "target_price",
    "exit_price",
    "exit_reason",
    "net_pnl",
    "r_multiple",
)
METRIC_SIGNATURE_KEYS = (
    "total_trades",
    "trades_per_year",
    "net_profit",
    "profit_factor",
    "expectancy_r",
    "max_drawdown",
    "max_drawdown_pct",
    "mar",
    "win_rate",
    "max_consecutive_losses",
    "apex_rule_violations",
    "apex_forced_flatten_trades",
)


def backtest_result_signature(result: dict[str, Any]) -> dict[str, Any]:
    trades = result.get("trades", pd.DataFrame())
    metrics = result.get("metrics", {})
    payload = {
        "metrics": {key: _json_value(metrics.get(key)) for key in METRIC_SIGNATURE_KEYS},
        "trades": _trade_rows(trades),
    }
    return {"hash": object_sha256(payload), "payload": payload}


def _trade_rows(trades: pd.DataFrame) -> list[dict[str, Any]]:
    if trades.empty:
        return []
    out = trades.copy()
    if "trade_id" in out.columns:
        out = out.sort_values("trade_id", kind="mergesort")
    rows = []
    for _, row in out.iterrows():
        rows.append({column: _json_value(row.get(column)) for column in TRADE_SIGNATURE_COLUMNS})
    return rows


def _json_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return round(value, 10)
    if hasattr(value, "item"):
        return _json_value(value.item())
    return value
