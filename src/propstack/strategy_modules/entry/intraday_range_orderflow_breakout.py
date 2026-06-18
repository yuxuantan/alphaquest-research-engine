from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class IntradayRangeOrderflowBreakoutEntry:
    name = "intraday_range_orderflow_breakout"

    _FLOW_COLUMNS = {
        "signed_volume": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }

    def __init__(self, params: dict):
        self.params = params
        self.state_by_day: dict = {}
        self.range_start = parse_time(params.get("range_start", "11:30:00"))
        self.range_end = parse_time(params.get("range_end", "13:00:00"))
        self.last_entry_time = parse_time(params.get("last_entry_time", "15:00:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.confirmation_minutes = float(params.get("confirmation_minutes", self.bar_interval_minutes))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.breakout_buffer = self.tick_size * int(params.get("breakout_buffer_ticks", 0))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.0))
        self.max_range_points = _optional_float(params.get("max_range_points"))
        self.min_range_points = float(params.get("min_range_points", 0.0))
        self.min_flow_volume = float(params.get("min_flow_volume", 0.0))
        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = self._bar_close_timestamp(timestamp)
        state = self._state(bar["session_date"])

        if state["completed"] or state["skip_day"]:
            return None

        if timestamp.time() < self.range_start:
            return None

        if timestamp.time() < self.range_end:
            state["range_bars"].append(bar)
            return None

        if state["intraday_range"] is None:
            state["intraday_range"] = self._build_intraday_range(state)
            if state["skip_day"] or state["intraday_range"] is None:
                state["completed"] = True
                return None

        if timestamp.time() >= self.last_entry_time or bar_close.time() > self.last_entry_time:
            state["completed"] = True
            return None

        state["confirmation_bars"].append(bar)
        if len(state["confirmation_bars"]) < self._confirmation_bar_count():
            return None

        signal = self._confirmation_signal(bar, state["intraday_range"], state["confirmation_bars"])
        if signal is not None:
            state["completed"] = True
            return signal
        state["confirmation_bars"] = []
        return None

    def _state(self, session_date):
        return self.state_by_day.setdefault(
            session_date,
            {
                "range_bars": [],
                "confirmation_bars": [],
                "intraday_range": None,
                "completed": False,
                "skip_day": False,
            },
        )

    def _confirmation_bar_count(self) -> int:
        return max(1, int(math.ceil(self.confirmation_minutes / self.bar_interval_minutes)))

    def _build_intraday_range(self, state: dict) -> dict | None:
        bars = state["range_bars"]
        if not bars:
            state["skip_day"] = True
            return None
        try:
            range_open = float(bars[0]["open"])
            range_high = max(float(bar["high"]) for bar in bars)
            range_low = min(float(bar["low"]) for bar in bars)
        except (KeyError, TypeError, ValueError):
            state["skip_day"] = True
            return None

        width = range_high - range_low
        values = [range_open, range_high, range_low, width]
        if not all(math.isfinite(value) for value in values) or range_open <= 0:
            state["skip_day"] = True
            return None
        if width < self.min_range_points:
            state["skip_day"] = True
        if self.max_range_points is not None and width > self.max_range_points:
            state["skip_day"] = True

        return {
            "open": range_open,
            "high": range_high,
            "low": range_low,
            "width": width,
            "width_pct_of_open": width / range_open,
            "start_timestamp": bars[0]["timestamp"],
            "end_timestamp": self._bar_close_timestamp(bars[-1]["timestamp"]),
        }

    def _confirmation_signal(
        self,
        bar: pd.Series,
        intraday_range: dict | None,
        confirmation_bars: list[pd.Series],
    ) -> Signal | None:
        if intraday_range is None:
            return None
        close = _finite_float(bar.get("close"))
        if close is None:
            return None

        direction, breakout_level, level_type = self._breakout_trigger(close, intraday_range)
        if direction is None:
            return None

        flow = self._confirmation_flow(confirmation_bars or [bar])
        if flow is None:
            return None
        signed_volume, total_volume, imbalance = flow
        if total_volume < self.min_flow_volume:
            return None
        if direction == "long" and imbalance < self.min_orderflow_imbalance:
            return None
        if direction == "short" and imbalance > -self.min_orderflow_imbalance:
            return None

        confirmation_start = confirmation_bars[0]["timestamp"] if confirmation_bars else bar["timestamp"]
        confirmation_end = self._bar_close_timestamp(bar["timestamp"])
        if confirmation_end.time() > self.last_entry_time:
            return None

        trigger_side = "upside" if direction == "long" else "downside"
        confirmation_high = max(float(confirmation_bar["high"]) for confirmation_bar in confirmation_bars)
        confirmation_low = min(float(confirmation_bar["low"]) for confirmation_bar in confirmation_bars)
        return Signal(
            direction=direction,
            level_type=level_type,
            swept_level=breakout_level,
            sweep_timestamp=intraday_range["start_timestamp"],
            sweep_high=intraday_range["high"],
            sweep_low=intraday_range["low"],
            reclaim_timestamp=confirmation_end,
            breakout_level=breakout_level,
            opening_range_high=intraday_range["high"],
            opening_range_low=intraday_range["low"],
            opening_range_open=intraday_range["open"],
            opening_range_width=intraday_range["width"],
            metadata={
                "intraday_range_start_timestamp": intraday_range["start_timestamp"],
                "intraday_range_end_timestamp": intraday_range["end_timestamp"],
                "intraday_range_width": intraday_range["width"],
                "intraday_range_width_pct_of_open": intraday_range["width_pct_of_open"],
                "confirmation_start_timestamp": confirmation_start,
                "confirmation_end_timestamp": confirmation_end,
                "confirmation_high": confirmation_high,
                "confirmation_low": confirmation_low,
                "confirmation_close": close,
                "breakout_timestamp": confirmation_end,
                "trigger_side": trigger_side,
                "flow_mode": self.flow_mode,
                "confirmation_signed_volume": signed_volume,
                "confirmation_flow_volume": total_volume,
                "confirmation_orderflow_imbalance": imbalance,
            },
            report_fields={
                "intraday_range_start_timestamp": intraday_range["start_timestamp"],
                "intraday_range_end_timestamp": intraday_range["end_timestamp"],
                "intraday_range_high": intraday_range["high"],
                "intraday_range_low": intraday_range["low"],
                "intraday_range_open": intraday_range["open"],
                "intraday_range_width": intraday_range["width"],
                "intraday_range_width_pct_of_open": intraday_range["width_pct_of_open"],
                "confirmation_start_timestamp": confirmation_start,
                "confirmation_end_timestamp": confirmation_end,
                "breakout_timestamp": confirmation_end,
                "breakout_level": breakout_level,
                "trigger_side": trigger_side,
                "flow_mode": self.flow_mode,
                "confirmation_signed_volume": signed_volume,
                "confirmation_flow_volume": total_volume,
                "confirmation_orderflow_imbalance": imbalance,
            },
        )

    def _breakout_trigger(
        self,
        close: float,
        intraday_range: dict,
    ) -> tuple[str | None, float | None, str | None]:
        high = float(intraday_range["high"])
        low = float(intraday_range["low"])
        if close > high + self.breakout_buffer and self.allow_long:
            return "long", high, "intraday_range_high_orderflow_breakout"
        if close < low - self.breakout_buffer and self.allow_short:
            return "short", low, "intraday_range_low_orderflow_breakout"
        return None, None, None

    def _confirmation_flow(self, bars: list[pd.Series]) -> tuple[float, float, float] | None:
        signed_col, total_col = self._FLOW_COLUMNS[self.flow_mode]
        signed_values = []
        total_values = []
        for bar in bars:
            signed = _finite_float(bar.get(signed_col))
            total = _finite_float(bar.get(total_col))
            if signed is None or total is None:
                return None
            signed_values.append(signed)
            total_values.append(total)
        signed_sum = float(sum(signed_values))
        total_sum = float(sum(total_values))
        if not math.isfinite(total_sum) or total_sum <= 0:
            return None
        imbalance = signed_sum / total_sum
        if not math.isfinite(imbalance):
            return None
        return signed_sum, total_sum, imbalance

    def _bar_close_timestamp(self, timestamp) -> pd.Timestamp:
        return pd.Timestamp(timestamp) + pd.Timedelta(minutes=self.bar_interval_minutes)

    def _validate(self) -> None:
        if self.range_end <= self.range_start:
            raise ValueError("entry.params.range_end must be after range_start.")
        if self.last_entry_time <= self.range_end:
            raise ValueError("entry.params.last_entry_time must be after range_end.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than 0.")
        if self.confirmation_minutes <= 0:
            raise ValueError("entry.params.confirmation_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be greater than 0.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("entry.params.min_orderflow_imbalance must be non-negative.")
        if self.min_range_points < 0:
            raise ValueError("entry.params.min_range_points must be non-negative.")
        if self.max_range_points is not None and self.max_range_points < self.min_range_points:
            raise ValueError("entry.params.max_range_points must be >= min_range_points.")
        if self.min_flow_volume < 0:
            raise ValueError("entry.params.min_flow_volume must be non-negative.")
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError(f"entry.params.flow_mode must be one of {sorted(self._FLOW_COLUMNS)}.")
        if self.max_trades_per_day < 1:
            raise ValueError("entry.params.max_trades_per_day must be at least 1.")


def _optional_float(value) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _finite_float(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
