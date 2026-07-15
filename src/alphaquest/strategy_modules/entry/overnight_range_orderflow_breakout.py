from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class OvernightRangeOrderflowBreakoutEntry:
    name = "overnight_range_orderflow_breakout"

    def __init__(self, params: dict):
        self.params = params
        self.start_time = parse_time(params.get("start_time", "09:35:00"))
        self.end_time = parse_time(params.get("end_time", "15:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.max_overnight_range_rank = float(params.get("max_overnight_range_rank", 0.30))
        self.min_overnight_range_points = float(params.get("min_overnight_range_points", 2.0))
        max_range = params.get("max_overnight_range_points")
        self.max_overnight_range_points = None if max_range is None else float(max_range)
        self.breakout_buffer_ticks = int(params.get("breakout_buffer_ticks", 1))
        self.orderflow_mode = str(params.get("orderflow_mode", "signed")).lower()
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.05))
        self.min_flow_volume = float(params.get("min_flow_volume", 0.0))
        self.state_by_day: dict = {}
        self.features = self._load_feature_csv(params.get("feature_csv"))
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _session_date(bar, timestamp)
        state = self.state_by_day.setdefault(session_date, {"completed": False})
        if state["completed"] or trades_today >= self.max_trades_per_day:
            return None
        bar_time = timestamp.time()
        if bar_time < self.start_time or bar_time > self.end_time:
            return None

        features = self.features.get(session_date)
        if features is None or not self._overnight_filter_allows(features):
            return None
        imbalance, flow_volume, signed_volume = self._flow_values(bar)
        if imbalance is None or flow_volume is None or flow_volume < self.min_flow_volume:
            return None

        close = _required_float(bar.get("close"), "close")
        high = _required_float(bar.get("high"), "high")
        low = _required_float(bar.get("low"), "low")
        overnight_high = features["overnight_high"]
        overnight_low = features["overnight_low"]
        buffer_points = self.breakout_buffer_ticks * self.tick_size

        direction = None
        breakout_level = None
        if (
            self.allow_long
            and close >= overnight_high + buffer_points
            and imbalance >= self.min_orderflow_imbalance
        ):
            direction = "long"
            breakout_level = overnight_high
        elif (
            self.allow_short
            and close <= overnight_low - buffer_points
            and imbalance <= -self.min_orderflow_imbalance
        ):
            direction = "short"
            breakout_level = overnight_low
        if direction is None:
            return None

        state["completed"] = True
        return self._signal(
            bar=bar,
            timestamp=timestamp,
            direction=direction,
            breakout_level=breakout_level,
            high=high,
            low=low,
            close=close,
            features=features,
            imbalance=imbalance,
            flow_volume=flow_volume,
            signed_volume=signed_volume,
        )

    def _signal(
        self,
        *,
        bar: pd.Series,
        timestamp: pd.Timestamp,
        direction: str,
        breakout_level: float,
        high: float,
        low: float,
        close: float,
        features: dict,
        imbalance: float,
        flow_volume: float,
        signed_volume: float,
    ) -> Signal:
        level_type = "overnight_high_compression_breakout" if direction == "long" else "overnight_low_compression_breakout"
        report_fields = {
            "feature_method": "completed_overnight_range_rank_with_completed_rth_bar_orderflow",
            "setup_mode": "overnight_range_orderflow_breakout",
            "orderflow_mode": self.orderflow_mode,
            "flow_confirmation": "breakout_direction_completed_bar_aggregate_flow",
            "overnight_high": features["overnight_high"],
            "overnight_low": features["overnight_low"],
            "overnight_midpoint": features["overnight_midpoint"],
            "overnight_range_points": features["overnight_range_points"],
            "overnight_range_rank_252": features["overnight_range_rank_252"],
            "max_overnight_range_rank": self.max_overnight_range_rank,
            "breakout_buffer_ticks": self.breakout_buffer_ticks,
            "breakout_level": breakout_level,
            "signal_close": close,
            "orderflow_imbalance": imbalance,
            "orderflow_volume": flow_volume,
            "orderflow_signed_volume": signed_volume,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "min_flow_volume": self.min_flow_volume,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=level_type,
            swept_level=breakout_level,
            sweep_timestamp=timestamp,
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=timestamp,
            breakout_level=breakout_level,
            metadata={
                "setup_mode": "overnight_range_orderflow_breakout",
                "orderflow_mode": self.orderflow_mode,
                "orderflow_imbalance": imbalance,
                "overnight_range_rank_252": features["overnight_range_rank_252"],
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _overnight_filter_allows(self, row: dict) -> bool:
        overnight_range = row["overnight_range_points"]
        rank = row["overnight_range_rank_252"]
        if overnight_range < self.min_overnight_range_points:
            return False
        if self.max_overnight_range_points is not None and overnight_range > self.max_overnight_range_points:
            return False
        return rank <= self.max_overnight_range_rank

    def _flow_values(self, bar: pd.Series) -> tuple[float | None, float | None, float | None]:
        if self.orderflow_mode in {"signed", "signed_volume", "all_volume"}:
            signed = _finite_float(bar.get("signed_volume"))
            volume = _finite_float(bar.get("volume"))
        elif self.orderflow_mode in {"large10", "large10_imbalance"}:
            signed = _finite_float(bar.get("large10_signed_volume"))
            volume = _finite_float(bar.get("large10_volume"))
        elif self.orderflow_mode in {"large20", "large20_imbalance"}:
            signed = _finite_float(bar.get("large20_signed_volume"))
            volume = _finite_float(bar.get("large20_volume"))
        else:
            raise ValueError(
                "orderflow_mode must be one of: signed, signed_volume, all_volume, "
                "large10, large10_imbalance, large20, large20_imbalance."
            )
        if signed is None or volume is None or volume <= 0:
            return None, volume, signed
        imbalance = signed / volume
        return (imbalance if math.isfinite(imbalance) else None), volume, signed

    def _load_feature_csv(self, path_value) -> dict:
        if not path_value:
            raise ValueError("feature_csv is required for overnight_range_orderflow_breakout.")
        path = Path(path_value)
        if not path.exists():
            raise FileNotFoundError(f"overnight feature_csv not found: {path}")
        df = pd.read_csv(path, parse_dates=["session_date"])
        required = {
            "session_date",
            "overnight_high",
            "overnight_low",
            "overnight_midpoint",
            "overnight_range_points",
            "overnight_range_rank_252",
        }
        missing = required.difference(df.columns)
        if missing:
            raise ValueError(f"overnight feature_csv missing columns: {sorted(missing)}")
        out = {}
        for row in df.to_dict("records"):
            session_date = pd.Timestamp(row["session_date"]).date()
            values = {name: _required_float(row.get(name), name) for name in required if name != "session_date"}
            if values["overnight_high"] <= values["overnight_low"]:
                continue
            out[session_date] = values
        return out

    def _validate(self) -> None:
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        if self.max_overnight_range_rank <= 0 or self.max_overnight_range_rank > 1:
            raise ValueError("max_overnight_range_rank must be in (0, 1].")
        if self.min_overnight_range_points < 0:
            raise ValueError("min_overnight_range_points must be non-negative.")
        if self.max_overnight_range_points is not None and self.max_overnight_range_points <= 0:
            raise ValueError("max_overnight_range_points must be positive when supplied.")
        if self.breakout_buffer_ticks < 0:
            raise ValueError("breakout_buffer_ticks must be non-negative.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("min_orderflow_imbalance must be non-negative.")
        if self.min_flow_volume < 0:
            raise ValueError("min_flow_volume must be non-negative.")
        if self.orderflow_mode not in {
            "signed",
            "signed_volume",
            "all_volume",
            "large10",
            "large10_imbalance",
            "large20",
            "large20_imbalance",
        }:
            raise ValueError("orderflow_mode is unsupported.")


def _session_date(bar: pd.Series, timestamp: pd.Timestamp):
    value = bar.get("session_date")
    if value is None or pd.isna(value):
        return timestamp.date()
    return pd.Timestamp(value).date()


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _required_float(value, name: str) -> float:
    out = _finite_float(value)
    if out is None:
        raise ValueError(f"entry bar is missing finite {name}.")
    return out
