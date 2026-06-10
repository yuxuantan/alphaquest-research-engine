from __future__ import annotations

from pathlib import Path
import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class MarketPlumbingPriorityEntry:
    name = "market_plumbing_priority"

    def __init__(self, params: dict):
        self.params = params
        self.feature_file = Path(params.get("feature_file", "data/external/market_plumbing_priority_features.csv"))
        self.direction = str(params.get("direction", "long")).lower()
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.legs = _parse_legs(params.get("legs"))
        _apply_flat_overrides(self.legs, params)
        self.priority_order = _parse_priority_order(params.get("priority_order"), self.legs)
        self.state_by_day: dict[pd.Timestamp, dict] = {}
        self.features_by_date = _load_feature_rows(
            self.feature_file,
            sorted({leg["feature_name"] for leg in self.legs.values()}),
        )
        if self.direction not in {"long", "short"}:
            raise ValueError("market_plumbing_priority direction must be long or short.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")

    def _state(self, session_date: pd.Timestamp) -> dict:
        return self.state_by_day.setdefault(session_date, self._initial_state(session_date))

    def _initial_state(self, session_date: pd.Timestamp) -> dict:
        row = self.features_by_date.get(session_date)
        selected = None
        if row:
            for key in self.priority_order:
                candidate = self._candidate(self.legs[key], row)
                if candidate is not None:
                    selected = candidate
                    break
        return {"signaled": False, "selected": selected}

    def _candidate(self, leg: dict, row: dict) -> dict | None:
        value = _finite_float(row.get(leg["feature_name"]))
        if value is None:
            return None
        active = value >= leg["threshold"] if leg["operator"] == ">=" else value <= leg["threshold"]
        if not active:
            return None
        return {**leg, "feature_value": value}

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        session_date = pd.Timestamp(bar["session_date"]).normalize()
        state = self._state(session_date)
        selected = state["selected"]
        if state["signaled"] or selected is None:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if bar_close.time() != selected["entry_time"]:
            return None

        state["signaled"] = True
        priority_label = ">".join(self.priority_order)
        flatten_label = selected["flatten_time"].strftime("%H:%M:%S")
        report_fields = {
            "academic_source_key": str(
                self.params.get(
                    "academic_source_key",
                    "brunnermeier_pedersen_2009_market_liquidity_funding_liquidity",
                )
            ),
            "external_dataset": str(
                self.params.get(
                    "external_dataset",
                    "cboe_cfe_vx_activity_nyfed_primary_dealer_statistics",
                )
            ),
            "external_feature_file": str(self.feature_file),
            "selected_market_plumbing_leg": selected["key"],
            "selected_market_plumbing_source": selected["source"],
            "market_plumbing_priority_order": priority_label,
            "feature_name": selected["feature_name"],
            "feature_operator": selected["operator"],
            "feature_threshold": selected["threshold"],
            "feature_value": selected["feature_value"],
            "feature_trade_date": session_date.date().isoformat(),
            "feature_availability_rule": selected["availability_rule"],
            "signal_stop_pct": selected["stop_pct"],
            "signal_target_r_multiple": selected["target_r_multiple"],
            "signal_flatten_time": flatten_label,
            "signal_timestamp": bar_close,
        }
        return Signal(
            direction=self.direction,
            level_type=f"market_plumbing_{selected['key']}",
            swept_level=float(bar["close"]),
            sweep_timestamp=bar_close,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=bar_close,
            metadata={
                "confirmation_high": float(bar["high"]),
                "confirmation_low": float(bar["low"]),
                "confirmation_close": float(bar["close"]),
                "selected_market_plumbing_leg": selected["key"],
                "selected_market_plumbing_source": selected["source"],
                "feature_name": selected["feature_name"],
                "feature_value": selected["feature_value"],
                "stop_pct": selected["stop_pct"],
                "target_r_multiple": selected["target_r_multiple"],
                "flatten_time": flatten_label,
            },
            report_fields=report_fields,
        )


def _load_feature_rows(path: Path, required_columns: list[str]) -> dict[pd.Timestamp, dict]:
    if not path.exists():
        raise FileNotFoundError(f"Market-plumbing feature file not found: {path}")
    df = pd.read_csv(path, parse_dates=["trade_date"])
    missing = {"trade_date", *required_columns} - set(df.columns)
    if missing:
        raise ValueError(f"Market-plumbing feature file is missing column(s): {sorted(missing)}")
    df = df.sort_values("trade_date").drop_duplicates("trade_date", keep="last")
    rows: dict[pd.Timestamp, dict] = {}
    for _, row in df.iterrows():
        trade_date = pd.Timestamp(row["trade_date"]).normalize()
        rows[trade_date] = {column: row[column] for column in required_columns}
    return rows


def _parse_priority_order(value, legs: dict[str, dict]) -> list[str]:
    if value is None:
        out = list(legs.keys())
    elif isinstance(value, str):
        out = [item.strip() for item in value.replace(">", ",").split(",") if item.strip()]
    else:
        out = [str(item).strip() for item in value if str(item).strip()]
    unknown = sorted(set(out) - set(legs))
    if unknown:
        raise ValueError(f"Unknown market-plumbing priority key(s): {unknown}")
    if not out:
        raise ValueError("priority_order must include at least one market-plumbing priority key.")
    return out


def _parse_legs(raw) -> dict[str, dict]:
    if not raw:
        raise ValueError("market_plumbing_priority requires at least one leg.")
    legs: dict[str, dict] = {}
    for item in raw:
        key = str(item.get("key", "")).strip()
        if not key:
            raise ValueError("Each market-plumbing leg requires a key.")
        if key in legs:
            raise ValueError(f"Duplicate market-plumbing leg key: {key}")
        operator = str(item.get("operator", "<=")).strip()
        if operator not in {"<=", ">="}:
            raise ValueError(f"{key} operator must be <= or >=.")
        stop_pct = float(item.get("stop_pct", 0.01))
        target_r = float(item.get("target_r_multiple", 2.0))
        if stop_pct <= 0 or target_r <= 0:
            raise ValueError(f"{key} stop_pct and target_r_multiple must be greater than 0.")
        legs[key] = {
            "key": key,
            "source": str(item.get("source", key)),
            "feature_name": str(item["feature_name"]),
            "operator": operator,
            "threshold": float(item["threshold"]),
            "entry_time": parse_time(item["entry_time"]),
            "flatten_time": parse_time(item["flatten_time"]),
            "stop_pct": stop_pct,
            "target_r_multiple": target_r,
            "availability_rule": str(item.get("availability_rule", "")),
        }
    return legs


def _apply_flat_overrides(legs: dict[str, dict], params: dict) -> None:
    for key, leg in legs.items():
        overrides = {
            "threshold": f"{key}_threshold",
            "stop_pct": f"{key}_stop_pct",
            "target_r_multiple": f"{key}_target_r_multiple",
        }
        for field, param_key in overrides.items():
            if param_key in params:
                leg[field] = float(params[param_key])
        if "entry_time" in leg and f"{key}_entry_time" in params:
            leg["entry_time"] = parse_time(params[f"{key}_entry_time"])
        if "flatten_time" in leg and f"{key}_flatten_time" in params:
            leg["flatten_time"] = parse_time(params[f"{key}_flatten_time"])
        if leg["stop_pct"] <= 0 or leg["target_r_multiple"] <= 0:
            raise ValueError(f"{key} stop_pct and target_r_multiple must be greater than 0.")


def _finite_float(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
