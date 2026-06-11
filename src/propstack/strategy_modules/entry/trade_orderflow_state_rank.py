from __future__ import annotations

from collections import deque
import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class TradeOrderflowStateRankEntry:
    name = "trade_orderflow_state_rank"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "bar_orderflow_state_rank"))
        self.entry_time = parse_time(params.get("entry_time", "13:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "14:31:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.feature_column = str(params.get("feature_column", "trade_orderflow_abs_imbalance_5"))
        self.filter_mode = str(params.get("filter_mode", "rank")).lower()
        self.rank_column = params.get("rank_column")
        self.rank_window = int(params.get("rank_window", 21))
        self.rank_min_periods = int(params.get("rank_min_periods", max(5, self.rank_window // 3)))
        self.threshold_side = str(params.get("threshold_side", "le")).lower()
        self.rank_threshold = float(params.get("rank_threshold", 0.2))
        self.value_threshold = float(params.get("value_threshold", params.get("feature_threshold", 0.0)))
        self.direction = str(params.get("direction", "long")).lower()
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.return_column = params.get("return_column")
        self.return_mode = str(params.get("return_mode", "none")).lower()
        self.min_return_ticks = float(params.get("min_return_ticks", 0.0))
        self.stop_pct = float(params.get("stop_pct", 0.01))
        self.target_r_multiple = float(params.get("target_r_multiple", 10.0))
        self._history: deque[float] = deque(maxlen=self.rank_window)

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None
        self._validate()

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        signal_timestamp = _session_timestamp(timestamp, self.entry_time)
        if bar_close != signal_timestamp:
            return None

        value = _finite_float(bar.get(self.feature_column))
        if value is None:
            return None
        rank = None
        if self.filter_mode == "rank":
            rank = self._rank_from_bar_or_history(bar, value)
            if rank is None:
                return None
            if not self._threshold_filter_passes(rank, self.rank_threshold):
                return None
        elif not self._threshold_filter_passes(value, self.value_threshold):
            return None
        if not self._return_filter_passes(bar):
            return None

        current_close = float(bar["close"])
        report_fields = {
            "setup_mode": self.setup_mode,
            "feature_method": "bar_level_orderflow_state_rank",
            "orderflow_state_filter_mode": self.filter_mode,
            "orderflow_state_feature_column": self.feature_column,
            "orderflow_state_feature_value": value,
            "orderflow_state_rank_column": self.rank_column,
            "orderflow_state_rank_window": self.rank_window,
            "orderflow_state_rank_min_periods": self.rank_min_periods,
            "orderflow_state_rank": rank,
            "orderflow_state_threshold_side": self.threshold_side,
            "orderflow_state_rank_threshold": self.rank_threshold,
            "orderflow_state_value_threshold": self.value_threshold,
            "return_column": self.return_column,
            "return_mode": self.return_mode,
            "min_return_ticks": self.min_return_ticks,
            "orderflow_signal_timestamp": signal_timestamp,
            "orderflow_intended_entry_timestamp": signal_timestamp,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "swept_level": current_close,
            "sweep_timestamp": timestamp,
            "sweep_high": float(bar["high"]),
            "sweep_low": float(bar["low"]),
            "reclaim_timestamp": signal_timestamp,
        }
        if self.return_column:
            report_fields["return_value"] = _finite_float(bar.get(str(self.return_column)))

        return Signal(
            direction=self.direction,
            level_type=f"trade_orderflow_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "filter_mode": self.filter_mode,
                "feature_column": self.feature_column,
                "feature_value": value,
                "rank_column": self.rank_column,
                "rank_window": self.rank_window,
                "rank": rank,
                "threshold_side": self.threshold_side,
                "rank_threshold": self.rank_threshold,
                "value_threshold": self.value_threshold,
                "return_column": self.return_column,
                "return_mode": self.return_mode,
                "min_return_ticks": self.min_return_ticks,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.filter_mode not in {"rank", "value"}:
            raise ValueError("filter_mode must be rank or value.")
        if self.rank_window <= 0:
            raise ValueError("rank_window must be greater than 0.")
        if self.rank_min_periods <= 0 or self.rank_min_periods > self.rank_window:
            raise ValueError("rank_min_periods must be in [1, rank_window].")
        if self.threshold_side not in {"ge", "le"}:
            raise ValueError("threshold_side must be ge or le.")
        if not (0 <= self.rank_threshold <= 1):
            raise ValueError("rank_threshold must be in [0, 1].")
        if not math.isfinite(self.value_threshold):
            raise ValueError("value_threshold must be finite.")
        if self.direction not in {"long", "short"}:
            raise ValueError("direction must be long or short.")
        if self.return_mode not in {"none", "up", "down"}:
            raise ValueError("return_mode must be one of: none, up, down.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")

    def _rank_against_history(self, value: float) -> float | None:
        history = [item for item in self._history if math.isfinite(item)]
        if len(history) < self.rank_min_periods:
            return None
        return float(sum(item <= value for item in history) / len(history))

    def _rank_from_bar_or_history(self, bar: pd.Series, value: float) -> float | None:
        if self.rank_column:
            return _finite_float(bar.get(str(self.rank_column)))
        rank = self._rank_against_history(value)
        self._history.append(value)
        return rank

    def _threshold_filter_passes(self, value: float, threshold: float) -> bool:
        if self.threshold_side == "ge":
            return value >= threshold
        return value <= threshold

    def _return_filter_passes(self, bar: pd.Series) -> bool:
        if self.return_mode == "none":
            return True
        if not self.return_column:
            return False
        value = _finite_float(bar.get(str(self.return_column)))
        if value is None:
            return False
        if self.return_mode == "up":
            return value >= self.min_return_ticks
        return value <= -self.min_return_ticks


def _session_timestamp(timestamp: pd.Timestamp, session_time) -> pd.Timestamp:
    return timestamp.replace(
        hour=session_time.hour,
        minute=session_time.minute,
        second=session_time.second,
        microsecond=0,
    )


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
