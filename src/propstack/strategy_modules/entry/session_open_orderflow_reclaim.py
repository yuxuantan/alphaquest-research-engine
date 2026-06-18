from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class SessionOpenOrderflowReclaimEntry:
    name = "session_open_orderflow_reclaim"

    _FLOW_COLUMNS = {
        "signed": ("signed_volume", "volume"),
        "signed_volume": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "session_open_orderflow_reclaim"))
        self.signal_start = parse_time(params.get("signal_start", "09:45:00"))
        self.signal_end = parse_time(params.get("signal_end", "15:15:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_open_extension_ticks = float(params.get("min_open_extension_ticks", 8))
        self.reclaim_buffer_ticks = float(params.get("reclaim_buffer_ticks", 0))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.10))
        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
        self.direction = str(params.get("direction", "both")).lower()
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        state = self._state(bar)
        signal = None

        if not state["signaled"] and self.signal_start <= bar_close.time() <= self.signal_end:
            signal = self._signal_from_prior_extension(bar, bar_close, state)
            if signal is not None:
                state["signaled"] = True

        self._update_session_extremes(bar, state)
        return signal

    def _state(self, bar: pd.Series) -> dict:
        session_date = bar["session_date"]
        state = self.state_by_day.get(session_date)
        if state is None:
            session_open = _finite_float(bar.get("open"))
            state = {
                "session_open": session_open,
                "prior_high": None,
                "prior_low": None,
                "up_extension_timestamp": None,
                "up_extension_high": None,
                "down_extension_timestamp": None,
                "down_extension_low": None,
                "signaled": False,
            }
            self.state_by_day[session_date] = state
        return state

    def _signal_from_prior_extension(self, bar: pd.Series, bar_close: pd.Timestamp, state: dict) -> Signal | None:
        session_open = _finite_float(state.get("session_open"))
        current_close = _finite_float(bar.get("close"))
        prior_high = _finite_float(state.get("prior_high"))
        prior_low = _finite_float(state.get("prior_low"))
        if None in {session_open, current_close}:
            return None

        flow = self._flow_values(bar)
        if flow is None:
            return None
        signed_volume, flow_volume, imbalance = flow

        extension_points = self.min_open_extension_ticks * self.tick_size
        reclaim_buffer = self.reclaim_buffer_ticks * self.tick_size
        long_ready = (
            prior_low is not None
            and prior_low <= session_open - extension_points
            and current_close >= session_open + reclaim_buffer
            and imbalance >= self.min_orderflow_imbalance
            and self.direction in {"long", "both"}
        )
        short_ready = (
            prior_high is not None
            and prior_high >= session_open + extension_points
            and current_close <= session_open - reclaim_buffer
            and imbalance <= -self.min_orderflow_imbalance
            and self.direction in {"short", "both"}
        )

        if long_ready:
            return self._build_signal(
                "long",
                bar,
                bar_close,
                state,
                signed_volume,
                flow_volume,
                imbalance,
                session_open,
                prior_low,
                "downside_extension_reclaim",
            )
        if short_ready:
            return self._build_signal(
                "short",
                bar,
                bar_close,
                state,
                signed_volume,
                flow_volume,
                imbalance,
                session_open,
                prior_high,
                "upside_extension_rejection",
            )
        return None

    def _build_signal(
        self,
        direction: str,
        bar: pd.Series,
        bar_close: pd.Timestamp,
        state: dict,
        signed_volume: float,
        flow_volume: float,
        imbalance: float,
        session_open: float,
        extension_extreme: float,
        trigger_type: str,
    ) -> Signal:
        if direction == "long":
            extension_timestamp = state.get("down_extension_timestamp")
            sweep_high = float(bar.get("high", session_open))
            sweep_low = _finite_float(state.get("down_extension_low")) or extension_extreme
        else:
            extension_timestamp = state.get("up_extension_timestamp")
            sweep_high = _finite_float(state.get("up_extension_high")) or extension_extreme
            sweep_low = float(bar.get("low", session_open))

        current_close = float(bar["close"])
        report_fields = {
            "setup_mode": self.setup_mode,
            "feature_method": "completed_bar_session_open_orderflow_reclaim",
            "session_open": session_open,
            "trigger_type": trigger_type,
            "direction": direction,
            "flow_mode": self.flow_mode,
            "signal_signed_volume": signed_volume,
            "signal_flow_volume": flow_volume,
            "signal_orderflow_imbalance": imbalance,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "min_open_extension_ticks": self.min_open_extension_ticks,
            "min_open_extension_points": self.min_open_extension_ticks * self.tick_size,
            "reclaim_buffer_ticks": self.reclaim_buffer_ticks,
            "current_close": current_close,
            "distance_from_open_points": current_close - session_open,
            "prior_high_before_signal": state.get("prior_high"),
            "prior_low_before_signal": state.get("prior_low"),
            "extension_timestamp": extension_timestamp,
            "extension_extreme": extension_extreme,
            "session_open_reclaim_signal_timestamp": bar_close,
            "session_open_reclaim_intended_entry_timestamp": bar_close,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=f"session_open_{trigger_type}_{self.flow_mode}",
            swept_level=session_open,
            sweep_timestamp=extension_timestamp,
            sweep_high=sweep_high,
            sweep_low=sweep_low,
            reclaim_timestamp=bar_close,
            metadata={
                "setup_mode": self.setup_mode,
                "session_open": session_open,
                "trigger_type": trigger_type,
                "flow_mode": self.flow_mode,
                "signal_orderflow_imbalance": imbalance,
                "extension_timestamp": extension_timestamp,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _flow_values(self, bar: pd.Series) -> tuple[float, float, float] | None:
        signed_col, total_col = self._FLOW_COLUMNS[self.flow_mode]
        signed = _finite_float(bar.get(signed_col))
        total = _finite_float(bar.get(total_col))
        if signed is None or total is None or total <= 0:
            return None
        imbalance = signed / total
        if not math.isfinite(imbalance):
            return None
        return signed, total, imbalance

    def _update_session_extremes(self, bar: pd.Series, state: dict) -> None:
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        timestamp = pd.Timestamp(bar["timestamp"])
        if high is not None and (state["prior_high"] is None or high > state["prior_high"]):
            state["prior_high"] = high
            state["up_extension_timestamp"] = timestamp
            state["up_extension_high"] = high
        if low is not None and (state["prior_low"] is None or low < state["prior_low"]):
            state["prior_low"] = low
            state["down_extension_timestamp"] = timestamp
            state["down_extension_low"] = low

    def _validate(self) -> None:
        if self.signal_end <= self.signal_start:
            raise ValueError("entry.params.signal_end must be after signal_start.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be greater than 0.")
        if self.min_open_extension_ticks < 0:
            raise ValueError("entry.params.min_open_extension_ticks must be non-negative.")
        if self.reclaim_buffer_ticks < 0:
            raise ValueError("entry.params.reclaim_buffer_ticks must be non-negative.")
        if self.min_orderflow_imbalance < 0 or self.min_orderflow_imbalance > 1:
            raise ValueError("entry.params.min_orderflow_imbalance must be between 0 and 1.")
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError("entry.params.flow_mode must be signed, signed_volume, large10, or large20.")
        if self.direction not in {"long", "short", "both"}:
            raise ValueError("entry.params.direction must be long, short, or both.")
        if self.max_trades_per_day < 1:
            raise ValueError("entry.params.max_trades_per_day must be at least 1.")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
