from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class GoldPlatinumRatioStateEntry:
    name = "gold_platinum_ratio_state"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "high_gp_risk_premium_long")).lower()
        self.feature_csv = str(
            params.get("feature_csv", "data/external/nq_gold_platinum_ratio_features_20110103_20260612.csv")
        )
        self.features = _load_features(self.feature_csv)
        self.availability_market = str(params.get("availability_market", "NQ"))
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.ratio_rank_threshold = float(params.get("ratio_rank_threshold", 0.65))
        self.change_rank_threshold = float(params.get("change_rank_threshold", 0.6))
        self.return_filter_ticks = float(params.get("return_filter_ticks", 0.0))
        self.return_column = str(params.get("return_column", "rth_return_since_open_ticks"))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.stop_pct = float(params.get("stop_pct", 0.004))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.5))
        self.state_by_day: dict[date, dict] = {}

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._validate()
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _date(bar["session_date"])
        state = self.state_by_day.setdefault(session_date, {"signaled": False, "session_open": None})
        if state["session_open"] is None:
            state["session_open"] = _finite_float(bar.get("open"))
        if state["signaled"]:
            return None

        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        signal_timestamp = timestamp.replace(
            hour=self.entry_time.hour,
            minute=self.entry_time.minute,
            second=self.entry_time.second,
            microsecond=0,
        )
        if bar_close != signal_timestamp:
            return None

        row = self.features.get(session_date)
        if row is None:
            return None
        direction, driver_column, driver_value = self._signal_direction(row, bar, state)
        if direction is None:
            return None

        current_close = float(bar["close"])
        report_fields = {
            "academic_source_key": "huang_kilic_2019_gold_platinum_expected_stock_returns",
            "setup_mode": self.setup_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "metal_observation_date": row.get("observation_date"),
            "availability_rule": (
                "latest gold/platinum futures closes strictly before "
                f"{self.availability_market} session_date"
            ),
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "gp_driver_column": driver_column,
            "gp_driver_value": driver_value,
            "ratio_rank_threshold": self.ratio_rank_threshold,
            "change_rank_threshold": self.change_rank_threshold,
            "return_filter_ticks": self.return_filter_ticks,
            "return_filter_value": self._return_filter_value(bar, state),
            "gold_close": row.get("gold_close"),
            "platinum_close": row.get("platinum_close"),
            "gold_platinum_ratio": row.get("gold_platinum_ratio"),
            "gp_change_1d": row.get("gp_change_1d"),
            "gp_change_5d": row.get("gp_change_5d"),
            "gp_ratio_rank_252": row.get("gp_ratio_rank_252"),
            "gp_change_1d_rank_252": row.get("gp_change_1d_rank_252"),
            "gp_change_5d_rank_252": row.get("gp_change_5d_rank_252"),
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"gold_platinum_ratio_state_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "gp_driver_column": driver_column,
                "gp_driver_value": driver_value,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _signal_direction(self, row: dict[str, float | str], bar: pd.Series, state: dict) -> tuple[str | None, str, float]:
        if self.setup_mode == "high_gp_risk_premium_long":
            column = "gp_ratio_rank_252"
            rank = _finite_float(row.get(column))
            if rank is not None and rank >= self.ratio_rank_threshold:
                return "long", column, rank
            return None, column, rank if rank is not None else float("nan")

        if self.setup_mode == "low_gp_complacency_short":
            column = "gp_ratio_rank_252"
            rank = _finite_float(row.get(column))
            if rank is not None and rank <= 1.0 - self.ratio_rank_threshold:
                return "short", column, rank
            return None, column, rank if rank is not None else float("nan")

        if self.setup_mode == "gp_rising_morning_weakness_short":
            column = "gp_change_5d_rank_252"
            rank = _finite_float(row.get(column))
            if rank is not None and rank >= self.change_rank_threshold and self._return_filter_passes(bar, state, "down"):
                return "short", column, rank
            return None, column, rank if rank is not None else float("nan")

        if self.setup_mode == "gp_falling_morning_strength_long":
            column = "gp_change_5d_rank_252"
            rank = _finite_float(row.get(column))
            if rank is not None and rank <= 1.0 - self.change_rank_threshold and self._return_filter_passes(bar, state, "up"):
                return "long", column, rank
            return None, column, rank if rank is not None else float("nan")

        if self.setup_mode == "gp_spike_tailrisk_long":
            column = "gp_change_1d_rank_252"
            rank = _finite_float(row.get(column))
            ratio_rank = _finite_float(row.get("gp_ratio_rank_252"))
            if rank is not None and ratio_rank is not None and rank >= self.change_rank_threshold and ratio_rank >= 0.5:
                return "long", column, rank
            return None, column, rank if rank is not None else float("nan")

        raise ValueError(f"Unsupported setup_mode for gold_platinum_ratio_state: {self.setup_mode}")

    def _return_filter_value(self, bar: pd.Series, state: dict) -> float | None:
        value = _finite_float(bar.get(self.return_column))
        if value is not None:
            return value
        if self.return_column != "rth_return_since_open_ticks":
            return None
        session_open = _finite_float(state.get("session_open"))
        close = _finite_float(bar.get("close"))
        if session_open is None or close is None or self.tick_size <= 0:
            return None
        return (close - session_open) / self.tick_size

    def _return_filter_passes(self, bar: pd.Series, state: dict, side: str) -> bool:
        value = self._return_filter_value(bar, state)
        if value is None:
            return False
        if side == "down":
            return value <= -self.return_filter_ticks
        return value >= self.return_filter_ticks

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if self.max_trades_per_day < 1:
            raise ValueError("max_trades_per_day must be at least 1.")
        for name, value in {
            "ratio_rank_threshold": self.ratio_rank_threshold,
            "change_rank_threshold": self.change_rank_threshold,
        }.items():
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1].")
        if self.return_filter_ticks < 0:
            raise ValueError("return_filter_ticks must be non-negative.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Gold/platinum ratio feature CSV not found: {path}")
    out: dict[date, dict[str, float | str]] = {}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            session_date = date.fromisoformat(str(row["session_date"]))
            out[session_date] = {
                key: (value if key == "observation_date" else _nan_float(value))
                for key, value in row.items()
                if key != "session_date"
            }
    return out


def _date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


def _nan_float(value) -> float:
    if value in {None, ""}:
        return float("nan")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _finite_float(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
