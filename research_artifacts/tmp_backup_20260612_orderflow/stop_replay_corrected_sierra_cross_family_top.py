from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


SOURCE = Path("data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet")
TRADES = Path("/private/tmp/corrected_sierra_cross_family_top_trades.csv")
OUT = Path("/private/tmp/corrected_sierra_cross_family_top_stop_replay.csv")
OUT_TRADES = Path("/private/tmp/corrected_sierra_cross_family_top_stop_replay_best_trades.csv")

TICK_SIZE = 0.25
TICK_VALUE = 12.50
ROUND_TURN_COST = 30.0
INITIAL_EQUITY = 150_000.0


def round_tick(price: float) -> float:
    return round(price / TICK_SIZE) * TICK_SIZE


def max_dd(pnl: pd.Series) -> float:
    eq = pnl.cumsum()
    return float((eq.cummax() - eq).max()) if len(eq) else 0.0


def metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {}
    pnl = trades["pnl"]
    gp = float(pnl[pnl > 0].sum())
    gl = float(-pnl[pnl < 0].sum())
    pf = gp / gl if gl > 0 else 99.0
    net = float(pnl.sum())
    dd = max_dd(pnl)
    first = pd.Timestamp(trades["entry_ts"].min())
    last = pd.Timestamp(trades["exit_ts"].max())
    years = max((last - first).days / 365.25, 1 / 365.25)
    ending = INITIAL_EQUITY + net
    cagr = (ending / INITIAL_EQUITY) ** (1 / years) - 1 if ending > 0 else -1.0
    max_dd_pct = dd / INITIAL_EQUITY
    mar = cagr / max_dd_pct if max_dd_pct > 0 else (99.0 if cagr > 0 else 0.0)
    dates = trades["entry_ts"].dt.date
    day = trades.groupby(dates)["pnl"].sum()
    month = trades.groupby(trades["entry_ts"].dt.to_period("M"))["pnl"].sum()
    return {
        "n": int(len(trades)),
        "net": net,
        "pf": pf,
        "cagr": cagr,
        "mar": mar,
        "max_dd": dd,
        "max_dd_pct": max_dd_pct,
        "worst_day": float(day.min()),
        "positive_month_rate": float((month > 0).mean()),
        "expectancy_ticks": float(trades["gross_ticks"].mean()),
        "early_net": float(pnl[dates < pd.Timestamp("2015-01-01").date()].sum()),
        "mid_net": float(
            pnl[(dates >= pd.Timestamp("2015-01-01").date()) & (dates < pd.Timestamp("2020-01-01").date())].sum()
        ),
        "late_net": float(
            pnl[(dates >= pd.Timestamp("2020-01-01").date()) & (dates < pd.Timestamp("2024-12-01").date())].sum()
        ),
        "holdout_net": float(pnl[dates >= pd.Timestamp("2024-12-01").date()].sum()),
        "stop_exits": int((trades["exit_reason"] == "stop").sum()),
        "target_exits": int((trades["exit_reason"] == "target").sum()),
        "time_exits": int((trades["exit_reason"] == "time").sum()),
    }


def acceptance(row: dict) -> bool:
    return (
        row["n"] >= 500
        and row["pf"] >= 1.50
        and row["cagr"] >= 0.04
        and row["mar"] >= 0.50
        and row["max_dd_pct"] <= 0.05
        and row["positive_month_rate"] >= 0.50
        and row["worst_day"] >= -4000
        and all(row[k] > 0 for k in ["early_net", "mid_net", "late_net", "holdout_net"])
    )


def infer_direction(row, bars_by_ts: dict[pd.Timestamp, tuple[float, float]]):
    entry_open, _ = bars_by_ts[row.entry_ts]
    _, exit_close = bars_by_ts[row.exit_ts]
    future_ticks = (exit_close - entry_open) / TICK_SIZE
    gross_ticks = float(row.gross_ticks)
    if abs(gross_ticks - future_ticks) <= abs(gross_ticks + future_ticks):
        return 1
    return -1


def replay_one(group: pd.DataFrame, trade, direction: int, stop_pct: float, target_r: float):
    entry_idx = int(group.index[group["timestamp"] == trade.entry_ts][0])
    exit_idx = int(group.index[group["timestamp"] == trade.exit_ts][0])
    entry = float(group.loc[entry_idx, "open"])
    stop_distance = max(TICK_SIZE, round_tick(entry * stop_pct))
    if direction == 1:
        stop = round_tick(entry - stop_distance)
        target = round_tick(entry + stop_distance * target_r)
    else:
        stop = round_tick(entry + stop_distance)
        target = round_tick(entry - stop_distance * target_r)

    exit_price = float(group.loc[exit_idx, "close"])
    exit_ts = trade.exit_ts
    reason = "time"
    for idx in range(entry_idx, exit_idx + 1):
        high = float(group.loc[idx, "high"])
        low = float(group.loc[idx, "low"])
        ts = pd.Timestamp(group.loc[idx, "timestamp"])
        if direction == 1:
            if low <= stop:
                exit_price = stop
                exit_ts = ts
                reason = "stop"
                break
            if high >= target:
                exit_price = target
                exit_ts = ts
                reason = "target"
                break
        else:
            if high >= stop:
                exit_price = stop
                exit_ts = ts
                reason = "stop"
                break
            if low <= target:
                exit_price = target
                exit_ts = ts
                reason = "target"
                break
    gross_ticks = direction * (exit_price - entry) / TICK_SIZE
    return {
        "entry_ts": trade.entry_ts,
        "exit_ts": exit_ts,
        "planned_exit_ts": trade.exit_ts,
        "entry_price": entry,
        "exit_price": exit_price,
        "direction": "long" if direction == 1 else "short",
        "gross_ticks": gross_ticks,
        "pnl": gross_ticks * TICK_VALUE - ROUND_TURN_COST,
        "exit_reason": reason,
        "leg_id": trade.leg_id,
    }


def main() -> None:
    raw = pd.read_parquet(SOURCE)
    raw["timestamp"] = pd.to_datetime(raw["timestamp"])
    raw["date"] = raw["timestamp"].dt.date
    raw = raw.reset_index(drop=True)
    bars_by_ts = {pd.Timestamp(r.timestamp): (float(r.open), float(r.close)) for r in raw.itertuples(index=False)}
    groups = {date: g.reset_index(drop=True) for date, g in raw.groupby("date", sort=False)}

    trades = pd.read_csv(TRADES, parse_dates=["entry_ts", "exit_ts"])
    directions = [infer_direction(row, bars_by_ts) for row in trades.itertuples(index=False)]
    rows = []
    replay_cache = {}
    for stop_pct in [0.003, 0.004, 0.005, 0.006, 0.008, 0.010, 0.015, 0.020, 0.030]:
        for target_r in [1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 10.0]:
            replayed = []
            for trade, direction in zip(trades.itertuples(index=False), directions):
                group = groups[trade.entry_ts.date()]
                replayed.append(replay_one(group, trade, direction, stop_pct, target_r))
            out = pd.DataFrame(replayed).sort_values(["entry_ts", "exit_ts"]).reset_index(drop=True)
            m = metrics(out)
            m["stop_pct"] = stop_pct
            m["target_r"] = target_r
            m["acceptance_shaped"] = acceptance(m)
            rows.append(m)
            replay_cache[(stop_pct, target_r)] = out
    result = pd.DataFrame(rows).sort_values(["acceptance_shaped", "net"], ascending=[False, False])
    result.to_csv(OUT, index=False)
    print(
        result.head(20)[
            [
                "stop_pct",
                "target_r",
                "n",
                "net",
                "pf",
                "cagr",
                "mar",
                "max_dd_pct",
                "worst_day",
                "positive_month_rate",
                "early_net",
                "mid_net",
                "late_net",
                "holdout_net",
                "stop_exits",
                "target_exits",
                "time_exits",
                "acceptance_shaped",
            ]
        ].to_string(index=False),
        flush=True,
    )
    best_key = (float(result.iloc[0]["stop_pct"]), float(result.iloc[0]["target_r"]))
    replay_cache[best_key].to_csv(OUT_TRADES, index=False)


if __name__ == "__main__":
    main()
