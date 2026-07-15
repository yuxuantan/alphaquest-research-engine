from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class FootprintAbsorptionInitiationEntry:
    name = "footprint_absorption_initiation"

    _MODES = {
        "prior_low_long",
        "prior_high_short",
        "prior_extreme_two_sided",
        "opening_range_two_sided",
        "rolling_range_two_sided",
        "round_number_two_sided",
        "session_open_two_sided",
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "rolling_range_two_sided")).lower()
        self.start_time = parse_time(params.get("start_time", "10:00:00"))
        self.end_time = parse_time(params.get("end_time", "15:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:30:00"))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_probe_ticks = float(params.get("min_probe_ticks", 1))
        self.confirmation_ticks = float(params.get("confirmation_ticks", 0))
        self.min_absorption_volume = float(params.get("min_absorption_volume", 20))
        self.opening_range_minutes = int(params.get("opening_range_minutes", 30))
        self.lookback_bars = int(params.get("lookback_bars", 60))
        self.round_number_interval = float(params.get("round_number_interval", 25.0))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = bar.get("session_date", timestamp.date())
        state = self.state_by_day.setdefault(session_date, {"bars": [], "signaled": False})
        signal = None
        if trades_today < self.max_trades_per_day and not state["signaled"]:
            signal = self._signal_from_completed_bar(bar, state["bars"])
            if signal is not None:
                state["signaled"] = True
        state["bars"].append(bar.copy())
        return signal

    def _signal_from_completed_bar(self, bar: pd.Series, prior_bars: list[pd.Series]) -> Signal | None:
        timestamp = pd.Timestamp(bar["timestamp"])
        if timestamp.time() < self.start_time or timestamp.time() > self.end_time:
            return None
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        open_ = _finite_float(bar.get("open"))
        close = _finite_float(bar.get("close"))
        if None in {high, low, open_, close}:
            return None

        candidates = self._candidate_levels(bar, prior_bars)
        for direction, level_type, level in candidates:
            if self._bar_confirms(direction, level, open_, high, low, close, bar):
                return self._signal(direction, level_type, level, bar)
        return None

    def _candidate_levels(self, bar: pd.Series, prior_bars: list[pd.Series]) -> list[tuple[str, str, float]]:
        if self.setup_mode == "prior_low_long":
            level = _finite_float(bar.get("prev_rth_low"))
            return [("long", "prior_low_footprint_absorption", level)] if level is not None else []
        if self.setup_mode == "prior_high_short":
            level = _finite_float(bar.get("prev_rth_high"))
            return [("short", "prior_high_footprint_absorption", level)] if level is not None else []
        if self.setup_mode == "prior_extreme_two_sided":
            low = _finite_float(bar.get("prev_rth_low"))
            high = _finite_float(bar.get("prev_rth_high"))
            candidates = []
            if low is not None:
                candidates.append(("long", "prior_low_footprint_absorption", low))
            if high is not None:
                candidates.append(("short", "prior_high_footprint_absorption", high))
            return candidates
        if self.setup_mode == "opening_range_two_sided":
            opening = self._opening_range(prior_bars)
            if opening is None:
                return []
            return [
                ("long", "opening_range_low_footprint_absorption", opening[0]),
                ("short", "opening_range_high_footprint_absorption", opening[1]),
            ]
        if self.setup_mode == "rolling_range_two_sided":
            if len(prior_bars) < self.lookback_bars:
                return []
            window = prior_bars[-self.lookback_bars :]
            low = min(float(item["low"]) for item in window)
            high = max(float(item["high"]) for item in window)
            return [
                ("long", "rolling_low_footprint_absorption", low),
                ("short", "rolling_high_footprint_absorption", high),
            ]
        if self.setup_mode == "round_number_two_sided":
            close = float(bar["close"])
            lower = math.floor(close / self.round_number_interval) * self.round_number_interval
            upper = math.ceil(close / self.round_number_interval) * self.round_number_interval
            return [
                ("long", "round_number_footprint_absorption", lower),
                ("short", "round_number_footprint_absorption", upper),
            ]
        if self.setup_mode == "session_open_two_sided":
            if not prior_bars:
                return []
            session_open = _finite_float(prior_bars[0].get("open"))
            if session_open is None:
                return []
            return [
                ("long", "session_open_footprint_absorption", session_open),
                ("short", "session_open_footprint_absorption", session_open),
            ]
        return []

    def _opening_range(self, prior_bars: list[pd.Series]) -> tuple[float, float] | None:
        if len(prior_bars) < self.opening_range_minutes:
            return None
        opening = prior_bars[: self.opening_range_minutes]
        return min(float(item["low"]) for item in opening), max(float(item["high"]) for item in opening)

    def _bar_confirms(
        self,
        direction: str,
        level: float,
        open_: float,
        high: float,
        low: float,
        close: float,
        bar: pd.Series,
    ) -> bool:
        probe = self.min_probe_ticks * self.tick_size
        confirm = self.confirmation_ticks * self.tick_size
        if direction == "long":
            if not self.allow_long:
                return False
            absorption = _finite_float(bar.get("footprint_absorption_long")) or 0.0
            volume = _finite_float(bar.get("footprint_max_sell_imbalance_volume")) or 0.0
            imbalance_price = _finite_float(bar.get("footprint_highest_sell_imbalance_price"))
            return (
                absorption > 0
                and volume >= self.min_absorption_volume
                and imbalance_price is not None
                and imbalance_price < close
                and low <= level - probe
                and close >= level + confirm
                and close > open_
            )
        if not self.allow_short:
            return False
        absorption = _finite_float(bar.get("footprint_absorption_short")) or 0.0
        volume = _finite_float(bar.get("footprint_max_buy_imbalance_volume")) or 0.0
        imbalance_price = _finite_float(bar.get("footprint_lowest_buy_imbalance_price"))
        return (
            absorption > 0
            and volume >= self.min_absorption_volume
            and imbalance_price is not None
            and imbalance_price > close
            and high >= level + probe
            and close <= level - confirm
            and close < open_
        )

    def _signal(self, direction: str, level_type: str, level: float, bar: pd.Series) -> Signal:
        volume_col = (
            "footprint_max_sell_imbalance_volume"
            if direction == "long"
            else "footprint_max_buy_imbalance_volume"
        )
        price_col = (
            "footprint_highest_sell_imbalance_price"
            if direction == "long"
            else "footprint_lowest_buy_imbalance_price"
        )
        report_fields = {
            "setup_mode": self.setup_mode,
            "aoi_level": level,
            "confirmation_ticks": self.confirmation_ticks,
            "min_probe_ticks": self.min_probe_ticks,
            "min_absorption_volume": self.min_absorption_volume,
            "footprint_absorption_volume": _finite_float(bar.get(volume_col)) or 0.0,
            "footprint_absorption_price": _finite_float(bar.get(price_col)) or 0.0,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=level_type,
            swept_level=level,
            sweep_timestamp=bar["timestamp"],
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=bar["timestamp"],
            metadata=report_fields.copy(),
            report_fields=report_fields,
        )

    def _validate(self) -> None:
        if self.setup_mode not in self._MODES:
            raise ValueError(f"entry.params.setup_mode must be one of {sorted(self._MODES)}.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be positive.")
        if self.min_probe_ticks < 0 or self.confirmation_ticks < 0:
            raise ValueError("entry probe/confirmation ticks must be non-negative.")
        if self.min_absorption_volume <= 0:
            raise ValueError("entry.params.min_absorption_volume must be positive.")
        if self.opening_range_minutes < 1:
            raise ValueError("entry.params.opening_range_minutes must be at least one.")
        if self.lookback_bars < 2:
            raise ValueError("entry.params.lookback_bars must be at least two.")
        if self.round_number_interval <= 0:
            raise ValueError("entry.params.round_number_interval must be positive.")
        if self.max_trades_per_day < 1:
            raise ValueError("entry.params.max_trades_per_day must be at least one.")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
