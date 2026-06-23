from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class LowToxicityAoiFalseBreakoutEntry:
    name = "low_toxicity_aoi_false_breakout"

    _MODES = {
        "market_aoi_false_breakout",
        "prior_extreme_false_breakout",
        "opening_range_false_breakout",
        "overnight_false_breakout",
        "value_area_false_breakout",
        "lvn_false_breakout",
        "poc_false_breakout",
        "all_aoi_false_breakout",
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "market_aoi_false_breakout")).lower()
        self.start_time = parse_time(params.get("start_time", "10:00:00"))
        self.end_time = parse_time(params.get("end_time", "15:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.opening_range_minutes = int(params.get("opening_range_minutes", 30))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_probe_ticks = float(params.get("min_probe_ticks", 1))
        self.confirmation_ticks = float(params.get("confirmation_ticks", 0))
        self.max_abs_delta_imbalance = float(params.get("max_abs_delta_imbalance", 0.12))
        self.large_volume_col = str(params.get("large_volume_col", "large20_volume"))
        self.max_large_volume_share = _optional_float(params.get("max_large_volume_share"))
        self.cached_profile_prefix = str(params.get("cached_profile_prefix", "prior_vap"))
        self.require_reversal_body = bool(params.get("require_reversal_body", True))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.current_session = None
        self.current_session_bars: list[pd.Series] = []
        self.signaled_sessions: set = set()
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._roll_session(bar)
        if not bool(bar.get("is_rth", False)):
            return None

        session_date = bar.get("session_date")
        signal_timestamp = pd.Timestamp(bar["timestamp"]) + pd.Timedelta(minutes=self.bar_interval_minutes)
        signal = None
        if session_date not in self.signaled_sessions and trades_today < self.max_trades_per_day:
            signal = self._signal_from_completed_bar(bar, signal_timestamp)
            if signal is not None:
                self.signaled_sessions.add(session_date)
        self.current_session_bars.append(bar.copy())
        return signal

    def _roll_session(self, bar: pd.Series) -> None:
        session_date = bar.get("session_date")
        if self.current_session is None:
            self.current_session = session_date
            return
        if session_date == self.current_session:
            return
        self.current_session = session_date
        self.current_session_bars = []

    def _signal_from_completed_bar(self, bar: pd.Series, signal_timestamp: pd.Timestamp) -> Signal | None:
        if signal_timestamp.time() < self.start_time or signal_timestamp.time() > self.end_time:
            return None
        values = self._bar_values(bar)
        if values is None:
            return None
        toxicity = self._toxicity_state(bar, values)
        if toxicity is None:
            return None

        for direction, aoi_type, level in self._candidate_aois(bar):
            if direction == "long" and not self.allow_long:
                continue
            if direction == "short" and not self.allow_short:
                continue
            if not self._false_breakout_confirms(direction, values, level):
                continue
            return self._signal(direction, aoi_type, level, bar, values, toxicity, signal_timestamp)
        return None

    def _candidate_aois(self, bar: pd.Series) -> list[tuple[str, str, float]]:
        candidates: list[tuple[str, str, float]] = []
        mode = self.setup_mode
        if mode in {"prior_extreme_false_breakout", "market_aoi_false_breakout", "all_aoi_false_breakout"}:
            self._append_candidate(candidates, "long", "prior_rth_low", bar.get("prev_rth_low"))
            self._append_candidate(candidates, "short", "prior_rth_high", bar.get("prev_rth_high"))
        if mode in {"opening_range_false_breakout", "market_aoi_false_breakout", "all_aoi_false_breakout"}:
            opening = self._opening_range()
            if opening is not None:
                candidates.append(("long", "opening_range_low", opening["low"]))
                candidates.append(("short", "opening_range_high", opening["high"]))
        if mode in {"overnight_false_breakout", "market_aoi_false_breakout", "all_aoi_false_breakout"}:
            self._append_candidate(candidates, "long", "overnight_low", bar.get("overnight_low"))
            self._append_candidate(candidates, "short", "overnight_high", bar.get("overnight_high"))
        if mode in {"value_area_false_breakout", "all_aoi_false_breakout"}:
            prefix = self.cached_profile_prefix
            self._append_candidate(candidates, "long", "prior_value_area_low", bar.get(f"{prefix}_val"))
            self._append_candidate(candidates, "short", "prior_value_area_high", bar.get(f"{prefix}_vah"))
        if mode in {"lvn_false_breakout", "all_aoi_false_breakout"}:
            prefix = self.cached_profile_prefix
            self._append_candidate(candidates, "long", "prior_lvn_near_low", bar.get(f"{prefix}_lvn_near_low"))
            self._append_candidate(candidates, "short", "prior_lvn_near_high", bar.get(f"{prefix}_lvn_near_high"))
        if mode in {"poc_false_breakout", "all_aoi_false_breakout"}:
            prefix = self.cached_profile_prefix
            poc = _finite_float(bar.get(f"{prefix}_poc"))
            if poc is not None:
                candidates.append(("long", "prior_poc_reclaim", poc))
                candidates.append(("short", "prior_poc_reject", poc))
        return candidates

    def _append_candidate(
        self,
        candidates: list[tuple[str, str, float]],
        direction: str,
        aoi_type: str,
        raw_level,
    ) -> None:
        level = _finite_float(raw_level)
        if level is not None:
            candidates.append((direction, aoi_type, level))

    def _opening_range(self) -> dict | None:
        if len(self.current_session_bars) < self.opening_range_minutes:
            return None
        first = self.current_session_bars[0]
        session_start = pd.Timestamp(first["timestamp"])
        opening_end = session_start + pd.Timedelta(minutes=self.opening_range_minutes)
        opening_bars = [bar for bar in self.current_session_bars if pd.Timestamp(bar["timestamp"]) < opening_end]
        if len(opening_bars) < self.opening_range_minutes:
            return None
        return {
            "high": max(float(bar["high"]) for bar in opening_bars),
            "low": min(float(bar["low"]) for bar in opening_bars),
        }

    def _bar_values(self, bar: pd.Series) -> dict[str, float] | None:
        values = {
            "open": _finite_float(bar.get("open")),
            "high": _finite_float(bar.get("high")),
            "low": _finite_float(bar.get("low")),
            "close": _finite_float(bar.get("close")),
            "volume": _finite_float(bar.get("volume")),
            "signed_volume": _finite_float(bar.get("signed_volume")),
        }
        if any(value is None for value in values.values()) or values["volume"] <= 0:
            return None
        return values

    def _toxicity_state(self, bar: pd.Series, values: dict[str, float]) -> dict[str, float] | None:
        delta_imbalance = values["signed_volume"] / values["volume"]
        if abs(delta_imbalance) > self.max_abs_delta_imbalance:
            return None
        large_volume = _finite_float(bar.get(self.large_volume_col))
        large_share = None
        if self.max_large_volume_share is not None:
            if large_volume is None:
                return None
            large_share = large_volume / values["volume"] if values["volume"] > 0 else None
            if large_share is None or large_share > self.max_large_volume_share:
                return None
        return {
            "delta_imbalance": delta_imbalance,
            "abs_delta_imbalance": abs(delta_imbalance),
            "large_volume": large_volume if large_volume is not None else 0.0,
            "large_volume_share": large_share if large_share is not None else 0.0,
        }

    def _false_breakout_confirms(self, direction: str, values: dict[str, float], level: float) -> bool:
        probe = self.min_probe_ticks * self.tick_size
        confirm = self.confirmation_ticks * self.tick_size
        if direction == "long":
            if not (values["low"] <= level - probe and values["close"] >= level + confirm):
                return False
            return not self.require_reversal_body or values["close"] > values["open"]
        if not (values["high"] >= level + probe and values["close"] <= level - confirm):
            return False
        return not self.require_reversal_body or values["close"] < values["open"]

    def _signal(
        self,
        direction: str,
        aoi_type: str,
        level: float,
        bar: pd.Series,
        values: dict[str, float],
        toxicity: dict[str, float],
        signal_timestamp: pd.Timestamp,
    ) -> Signal:
        fields = {
            "setup_mode": self.setup_mode,
            "aoi_type": aoi_type,
            "aoi_level": level,
            "min_probe_ticks": self.min_probe_ticks,
            "confirmation_ticks": self.confirmation_ticks,
            "max_abs_delta_imbalance": self.max_abs_delta_imbalance,
            "delta_imbalance": toxicity["delta_imbalance"],
            "abs_delta_imbalance": toxicity["abs_delta_imbalance"],
            "large_volume_col": self.large_volume_col,
            "max_large_volume_share": self.max_large_volume_share,
            "large_volume": toxicity["large_volume"],
            "large_volume_share": toxicity["large_volume_share"],
            "signal_timestamp": signal_timestamp,
            "signal_close_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "source_quality_label": "completed-bar low-toxicity signed-flow AOI false-breakout proxy",
        }
        return Signal(
            direction=direction,
            level_type=f"{aoi_type}_low_toxicity_false_breakout",
            swept_level=level,
            sweep_timestamp=bar["timestamp"],
            sweep_high=values["high"],
            sweep_low=values["low"],
            reclaim_timestamp=signal_timestamp,
            metadata=fields.copy(),
            report_fields=fields,
        )

    def _validate(self) -> None:
        if self.setup_mode not in self._MODES:
            raise ValueError(f"entry.params.setup_mode must be one of {sorted(self._MODES)}.")
        if self.end_time <= self.start_time:
            raise ValueError("entry.params.end_time must be after start_time.")
        if self.bar_interval_minutes <= 0 or self.tick_size <= 0:
            raise ValueError("entry.params bar_interval_minutes and tick_size must be positive.")
        if self.opening_range_minutes < 1:
            raise ValueError("entry.params.opening_range_minutes must be positive.")
        if self.min_probe_ticks < 0 or self.confirmation_ticks < 0:
            raise ValueError("entry.params probe and confirmation thresholds must be non-negative.")
        if not 0 <= self.max_abs_delta_imbalance <= 1:
            raise ValueError("entry.params.max_abs_delta_imbalance must be between zero and one.")
        if self.max_large_volume_share is not None and not 0 <= self.max_large_volume_share <= 1:
            raise ValueError("entry.params.max_large_volume_share must be between zero and one.")
        if self.max_trades_per_day < 1:
            raise ValueError("entry.params.max_trades_per_day must be at least one.")


def _optional_float(value) -> float | None:
    if value is None or value == "":
        return None
    return _finite_float(value)


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
