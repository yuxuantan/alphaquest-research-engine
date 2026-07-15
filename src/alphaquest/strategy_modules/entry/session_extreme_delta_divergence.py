from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class SessionExtremeDeltaDivergenceEntry:
    name = "session_extreme_delta_divergence"

    _FLOW_COLUMNS = {
        "signed": ("signed_volume", "volume"),
        "signed_volume": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "session_extreme_delta_divergence")).lower()
        self.direction_mode = str(params.get("direction_mode", "two_sided")).lower()
        self.start_time = parse_time(params.get("start_time", "10:00:00"))
        self.end_time = parse_time(params.get("end_time", "15:15:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_bars_since_open = int(params.get("min_bars_since_open", 20))
        self.min_extreme_break_ticks = float(params.get("min_extreme_break_ticks", 1))
        self.close_reclaim_tolerance_ticks = float(params.get("close_reclaim_tolerance_ticks", 8))
        self.max_delta_progress_ratio = float(params.get("max_delta_progress_ratio", 0.05))
        self.flow_mode = str(params.get("flow_mode", "signed")).lower()
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        session_date = bar.get("session_date", timestamp.date())
        state = self._state(session_date)

        signed_volume, flow_volume = self._flow_values(bar)
        signal = None
        if (
            not state["signaled"]
            and trades_today < self.max_trades_per_day
            and self.start_time <= bar_close.time() <= self.end_time
            and state["bars_seen"] >= self.min_bars_since_open
            and signed_volume is not None
            and flow_volume is not None
            and state["prior_high"] is not None
            and state["prior_low"] is not None
        ):
            signal = self._signal_from_completed_bar(bar, bar_close, state, signed_volume, flow_volume)
            if signal is not None:
                state["signaled"] = True

        if signed_volume is not None and flow_volume is not None:
            self._update_state(state, bar, signed_volume, flow_volume)
        return signal

    def _state(self, session_date) -> dict:
        return self.state_by_day.setdefault(
            session_date,
            {
                "bars_seen": 0,
                "signaled": False,
                "cum_delta": 0.0,
                "cum_volume": 0.0,
                "prior_high": None,
                "prior_low": None,
                "cum_delta_at_high": 0.0,
                "cum_volume_at_high": 0.0,
                "cum_delta_at_low": 0.0,
                "cum_volume_at_low": 0.0,
                "high_timestamp": None,
                "low_timestamp": None,
            },
        )

    def _signal_from_completed_bar(
        self,
        bar: pd.Series,
        signal_timestamp: pd.Timestamp,
        state: dict,
        signed_volume: float,
        flow_volume: float,
    ) -> Signal | None:
        current_cum_delta = state["cum_delta"] + signed_volume
        current_cum_volume = state["cum_volume"] + flow_volume
        min_break = self.min_extreme_break_ticks * self.tick_size
        close_tolerance = self.close_reclaim_tolerance_ticks * self.tick_size
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])

        if self.direction_mode in {"two_sided", "high_short"}:
            prior_high = float(state["prior_high"])
            price_break = high - prior_high
            delta_progress = current_cum_delta - state["cum_delta_at_high"]
            volume_progress = max(current_cum_volume - state["cum_volume_at_high"], 1.0)
            delta_progress_ratio = delta_progress / volume_progress
            if (
                price_break >= min_break
                and close <= prior_high + close_tolerance
                and delta_progress_ratio <= self.max_delta_progress_ratio
            ):
                return self._signal(
                    direction="short",
                    level=prior_high,
                    signal_timestamp=signal_timestamp,
                    bar=bar,
                    state=state,
                    price_break_ticks=price_break / self.tick_size,
                    delta_progress=delta_progress,
                    volume_progress=volume_progress,
                    delta_progress_ratio=delta_progress_ratio,
                )

        if self.direction_mode in {"two_sided", "low_long"}:
            prior_low = float(state["prior_low"])
            price_break = prior_low - low
            delta_progress = current_cum_delta - state["cum_delta_at_low"]
            volume_progress = max(current_cum_volume - state["cum_volume_at_low"], 1.0)
            delta_progress_ratio = delta_progress / volume_progress
            if (
                price_break >= min_break
                and close >= prior_low - close_tolerance
                and delta_progress_ratio >= -self.max_delta_progress_ratio
            ):
                return self._signal(
                    direction="long",
                    level=prior_low,
                    signal_timestamp=signal_timestamp,
                    bar=bar,
                    state=state,
                    price_break_ticks=price_break / self.tick_size,
                    delta_progress=delta_progress,
                    volume_progress=volume_progress,
                    delta_progress_ratio=delta_progress_ratio,
                )
        return None

    def _signal(
        self,
        direction: str,
        level: float,
        signal_timestamp: pd.Timestamp,
        bar: pd.Series,
        state: dict,
        price_break_ticks: float,
        delta_progress: float,
        volume_progress: float,
        delta_progress_ratio: float,
    ) -> Signal:
        return Signal(
            direction=direction,
            level_type=f"session_extreme_delta_divergence_{self.setup_mode}",
            swept_level=level,
            sweep_timestamp=bar["timestamp"],
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "direction_mode": self.direction_mode,
                "flow_mode": self.flow_mode,
                "reference_level": level,
                "price_break_ticks": price_break_ticks,
                "delta_progress_ratio": delta_progress_ratio,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields={
                "academic_source_key": "cont_2014_ofi_kavajecz_2004_liquidity_levels",
                "setup_mode": self.setup_mode,
                "direction_mode": self.direction_mode,
                "signal_timestamp": signal_timestamp,
                "flow_mode": self.flow_mode,
                "reference_level": level,
                "session_prior_high": state["prior_high"],
                "session_prior_low": state["prior_low"],
                "session_prior_high_timestamp": state["high_timestamp"],
                "session_prior_low_timestamp": state["low_timestamp"],
                "signal_bar_high": float(bar["high"]),
                "signal_bar_low": float(bar["low"]),
                "signal_bar_close": float(bar["close"]),
                "price_break_ticks": price_break_ticks,
                "min_extreme_break_ticks": self.min_extreme_break_ticks,
                "close_reclaim_tolerance_ticks": self.close_reclaim_tolerance_ticks,
                "cum_delta_before_signal_bar": state["cum_delta"],
                "cum_volume_before_signal_bar": state["cum_volume"],
                "delta_progress": delta_progress,
                "volume_progress": volume_progress,
                "delta_progress_ratio": delta_progress_ratio,
                "max_delta_progress_ratio": self.max_delta_progress_ratio,
                "min_bars_since_open": self.min_bars_since_open,
                "bars_seen_before_signal": state["bars_seen"],
                "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
        )

    def _update_state(self, state: dict, bar: pd.Series, signed_volume: float, flow_volume: float) -> None:
        state["bars_seen"] += 1
        state["cum_delta"] += signed_volume
        state["cum_volume"] += flow_volume
        high = float(bar["high"])
        low = float(bar["low"])
        if state["prior_high"] is None or high > state["prior_high"]:
            state["prior_high"] = high
            state["cum_delta_at_high"] = state["cum_delta"]
            state["cum_volume_at_high"] = state["cum_volume"]
            state["high_timestamp"] = bar["timestamp"]
        if state["prior_low"] is None or low < state["prior_low"]:
            state["prior_low"] = low
            state["cum_delta_at_low"] = state["cum_delta"]
            state["cum_volume_at_low"] = state["cum_volume"]
            state["low_timestamp"] = bar["timestamp"]

    def _flow_values(self, bar: pd.Series) -> tuple[float | None, float | None]:
        signed_col, volume_col = self._FLOW_COLUMNS[self.flow_mode]
        signed = _finite_float(bar.get(signed_col))
        volume = _finite_float(bar.get(volume_col))
        if signed is None or volume is None or volume <= 0:
            return None, None
        return signed, volume

    def _validate(self) -> None:
        if self.direction_mode not in {"two_sided", "high_short", "low_long"}:
            raise ValueError("entry.params.direction_mode must be two_sided, high_short, or low_long.")
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError("entry.params.flow_mode must be signed, signed_volume, large10, or large20.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be greater than 0.")
        if self.min_bars_since_open < 1:
            raise ValueError("entry.params.min_bars_since_open must be at least 1.")
        if self.min_extreme_break_ticks < 0:
            raise ValueError("entry.params.min_extreme_break_ticks must be non-negative.")
        if self.close_reclaim_tolerance_ticks < 0:
            raise ValueError("entry.params.close_reclaim_tolerance_ticks must be non-negative.")
        if self.max_delta_progress_ratio < 0 or not math.isfinite(self.max_delta_progress_ratio):
            raise ValueError("entry.params.max_delta_progress_ratio must be finite and non-negative.")
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
