from __future__ import annotations

import math
from collections import deque
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class SessionLiquidityFvgReversalEntry:
    name = "session_liquidity_fvg_reversal"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "asia_two_sided_fvg_rejection")).lower()
        self.setup_start_time = parse_time(params.get("setup_start_time", "09:30:00"))
        self.start_time = parse_time(params.get("start_time", "09:45:00"))
        self.end_time = parse_time(params.get("end_time", "12:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.bar_interval_minutes = int(params.get("bar_interval_minutes", 5))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.sweep_buffer_ticks = int(params.get("sweep_buffer_ticks", 0))
        self.reclaim_close_buffer_ticks = int(params.get("reclaim_close_buffer_ticks", 0))
        self.min_gap_ticks = int(params.get("min_gap_ticks", 2))
        self.max_reclaim_bars = int(params.get("max_reclaim_bars", 4))
        self.max_fvg_retest_bars = int(params.get("max_fvg_retest_bars", 6))
        self.features = self._load_feature_csv(params.get("feature_csv"))
        self.state_by_day: dict = {}
        self._bars_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _date(bar.get("session_date", timestamp.date()))
        features = self.features.get(session_date)
        if features is None:
            return None

        state = self.state_by_day.setdefault(session_date, self._new_state())
        bars = self._bars_by_day.setdefault(session_date, deque(maxlen=3))
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        signal = None
        if trades_today < self.max_trades_per_day and not state["signaled"]:
            self._record_sweeps(state, features, bar, timestamp, bar_close)
            self._record_fvg_after_sweep(state, bars, bar, timestamp)
            signal = self._maybe_signal(state, features, bar, timestamp, bar_close)
        bars.append(
            {
                "timestamp": timestamp,
                "high": _required_float(bar.get("high"), "high"),
                "low": _required_float(bar.get("low"), "low"),
                "close": _required_float(bar.get("close"), "close"),
            }
        )
        return signal

    def _new_state(self) -> dict:
        return {
            "signaled": False,
            "short": {"swept": False, "bars_since_sweep": 0, "gap": None},
            "long": {"swept": False, "bars_since_sweep": 0, "gap": None},
        }

    def _record_sweeps(
        self,
        state: dict,
        features: dict,
        bar: pd.Series,
        timestamp: pd.Timestamp,
        bar_close: pd.Timestamp,
    ) -> None:
        if bar_close.time() < self.setup_start_time or bar_close.time() > self.end_time:
            return
        high = _required_float(bar.get("high"), "high")
        low = _required_float(bar.get("low"), "low")
        close = _required_float(bar.get("close"), "close")
        buffer = self.sweep_buffer_ticks * self.tick_size

        if self._allows_short():
            level, level_type = self._high_reference(features)
            short = state["short"]
            if high >= level + buffer:
                if not short["swept"]:
                    short.update(
                        {
                            "swept": True,
                            "bars_since_sweep": 0,
                            "reference_level": level,
                            "reference_type": level_type,
                            "sweep_timestamp": timestamp,
                            "protected_extreme": high,
                            "sweep_close": close,
                        }
                    )
                else:
                    short["protected_extreme"] = max(float(short["protected_extreme"]), high)

        if self._allows_long():
            level, level_type = self._low_reference(features)
            long = state["long"]
            if low <= level - buffer:
                if not long["swept"]:
                    long.update(
                        {
                            "swept": True,
                            "bars_since_sweep": 0,
                            "reference_level": level,
                            "reference_type": level_type,
                            "sweep_timestamp": timestamp,
                            "protected_extreme": low,
                            "sweep_close": close,
                        }
                    )
                else:
                    long["protected_extreme"] = min(float(long["protected_extreme"]), low)

    def _record_fvg_after_sweep(self, state: dict, bars: deque, bar: pd.Series, timestamp: pd.Timestamp) -> None:
        if len(bars) < 2:
            return
        two_back = bars[-2]
        high = _required_float(bar.get("high"), "high")
        low = _required_float(bar.get("low"), "low")
        min_gap = self.min_gap_ticks * self.tick_size

        short = state["short"]
        if self._uses_fvg() and short.get("swept") and not short.get("gap"):
            gap_points = float(two_back["low"]) - high
            if gap_points >= min_gap:
                short["gap"] = {
                    "gap_type": "bearish_fvg",
                    "bottom": high,
                    "top": float(two_back["low"]),
                    "created_timestamp": timestamp,
                    "bars_since_created": 0,
                }

        long = state["long"]
        if self._uses_fvg() and long.get("swept") and not long.get("gap"):
            gap_points = low - float(two_back["high"])
            if gap_points >= min_gap:
                long["gap"] = {
                    "gap_type": "bullish_fvg",
                    "bottom": float(two_back["high"]),
                    "top": low,
                    "created_timestamp": timestamp,
                    "bars_since_created": 0,
                }

    def _maybe_signal(
        self,
        state: dict,
        features: dict,
        bar: pd.Series,
        timestamp: pd.Timestamp,
        bar_close: pd.Timestamp,
    ) -> Signal | None:
        if bar_close.time() < self.start_time or bar_close.time() > self.end_time:
            self._age_state(state)
            return None
        if "failed_sweep" in self.setup_mode:
            signal = self._failed_sweep_signal(state, features, bar, timestamp, bar_close)
        else:
            signal = self._fvg_rejection_signal(state, features, bar, timestamp, bar_close)
        self._age_state(state)
        if signal is not None:
            state["signaled"] = True
        return signal

    def _failed_sweep_signal(
        self,
        state: dict,
        features: dict,
        bar: pd.Series,
        timestamp: pd.Timestamp,
        bar_close: pd.Timestamp,
    ) -> Signal | None:
        close = _required_float(bar.get("close"), "close")
        buffer = self.reclaim_close_buffer_ticks * self.tick_size
        short = state["short"]
        if (
            self._allows_short()
            and short.get("swept")
            and int(short.get("bars_since_sweep", 0)) <= self.max_reclaim_bars
            and close <= float(short["reference_level"]) - buffer
        ):
            return self._signal("short", short, features, bar, timestamp, bar_close, "failed_session_liquidity_sweep")
        long = state["long"]
        if (
            self._allows_long()
            and long.get("swept")
            and int(long.get("bars_since_sweep", 0)) <= self.max_reclaim_bars
            and close >= float(long["reference_level"]) + buffer
        ):
            return self._signal("long", long, features, bar, timestamp, bar_close, "failed_session_liquidity_sweep")
        return None

    def _fvg_rejection_signal(
        self,
        state: dict,
        features: dict,
        bar: pd.Series,
        timestamp: pd.Timestamp,
        bar_close: pd.Timestamp,
    ) -> Signal | None:
        high = _required_float(bar.get("high"), "high")
        low = _required_float(bar.get("low"), "low")
        close = _required_float(bar.get("close"), "close")
        buffer = self.reclaim_close_buffer_ticks * self.tick_size

        short = state["short"]
        short_gap = short.get("gap")
        if self._allows_short() and short_gap and 0 < int(short_gap["bars_since_created"]) <= self.max_fvg_retest_bars:
            gap_bottom = float(short_gap["bottom"])
            if high >= gap_bottom and close <= gap_bottom - buffer:
                return self._signal("short", short, features, bar, timestamp, bar_close, "session_liquidity_fvg_rejection")

        long = state["long"]
        long_gap = long.get("gap")
        if self._allows_long() and long_gap and 0 < int(long_gap["bars_since_created"]) <= self.max_fvg_retest_bars:
            gap_top = float(long_gap["top"])
            if low <= gap_top and close >= gap_top + buffer:
                return self._signal("long", long, features, bar, timestamp, bar_close, "session_liquidity_fvg_rejection")
        return None

    def _signal(
        self,
        direction: str,
        side: dict,
        features: dict,
        bar: pd.Series,
        timestamp: pd.Timestamp,
        bar_close: pd.Timestamp,
        trigger_type: str,
    ) -> Signal:
        level = float(side["reference_level"])
        protected = float(side["protected_extreme"])
        gap = side.get("gap") or {}
        report_fields = {
            "academic_source_key": "chartfanatics_jadecap_session_liquidity_fvg_osler_lo_mamaysky_wang",
            "setup_mode": self.setup_mode,
            "trigger_type": trigger_type,
            "liquidity_reference_type": side["reference_type"],
            "liquidity_reference_level": level,
            "liquidity_sweep_timestamp": side["sweep_timestamp"],
            "protected_extreme": protected,
            "signal_timestamp": bar_close,
            "intended_entry_timestamp": bar_close,
            "asia_high": features["asia_high"],
            "asia_low": features["asia_low"],
            "london_high": features["london_high"],
            "london_low": features["london_low"],
            "combined_high": features["combined_high"],
            "combined_low": features["combined_low"],
            "session_level_availability_rule": "Asian and London levels end no later than 09:29 America/New_York before RTH signals",
            "sweep_buffer_ticks": self.sweep_buffer_ticks,
            "reclaim_close_buffer_ticks": self.reclaim_close_buffer_ticks,
            "min_gap_ticks": self.min_gap_ticks,
            "max_reclaim_bars": self.max_reclaim_bars,
            "max_fvg_retest_bars": self.max_fvg_retest_bars,
            "fvg_type": gap.get("gap_type"),
            "fvg_bottom": gap.get("bottom"),
            "fvg_top": gap.get("top"),
            "fvg_created_timestamp": gap.get("created_timestamp"),
            "signal_close": _required_float(bar.get("close"), "close"),
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=f"{trigger_type}_{side['reference_type']}_{direction}",
            swept_level=level,
            sweep_timestamp=side["sweep_timestamp"],
            sweep_high=protected if direction == "short" else _required_float(bar.get("high"), "high"),
            sweep_low=protected if direction == "long" else _required_float(bar.get("low"), "low"),
            reclaim_timestamp=bar_close,
            breakout_level=float((gap.get("bottom") if direction == "short" else gap.get("top")) or level),
            metadata={
                "setup_mode": self.setup_mode,
                "trigger_type": trigger_type,
                "liquidity_reference_type": side["reference_type"],
                "liquidity_reference_level": level,
                "protected_extreme": protected,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _age_state(self, state: dict) -> None:
        for side_name in ("short", "long"):
            side = state[side_name]
            if side.get("swept"):
                side["bars_since_sweep"] = int(side.get("bars_since_sweep", 0)) + 1
            gap = side.get("gap")
            if gap:
                gap["bars_since_created"] = int(gap.get("bars_since_created", 0)) + 1

    def _high_reference(self, features: dict) -> tuple[float, str]:
        if "london" in self.setup_mode:
            return features["london_high"], "london_high"
        if "combined" in self.setup_mode:
            return features["combined_high"], "combined_high"
        return features["asia_high"], "asia_high"

    def _low_reference(self, features: dict) -> tuple[float, str]:
        if "london" in self.setup_mode:
            return features["london_low"], "london_low"
        if "combined" in self.setup_mode:
            return features["combined_low"], "combined_low"
        return features["asia_low"], "asia_low"

    def _allows_short(self) -> bool:
        return "high" in self.setup_mode or "short" in self.setup_mode or "two_sided" in self.setup_mode

    def _allows_long(self) -> bool:
        return "low" in self.setup_mode or "long" in self.setup_mode or "two_sided" in self.setup_mode

    def _uses_fvg(self) -> bool:
        return "fvg" in self.setup_mode

    def _load_feature_csv(self, path_value) -> dict:
        if not path_value:
            raise ValueError("feature_csv is required for session_liquidity_fvg_reversal.")
        path = Path(path_value)
        if not path.exists():
            raise FileNotFoundError(f"session liquidity feature_csv not found: {path}")
        df = pd.read_csv(path, parse_dates=["session_date"])
        required = {
            "session_date",
            "asia_high",
            "asia_low",
            "london_high",
            "london_low",
            "combined_high",
            "combined_low",
        }
        missing = required.difference(df.columns)
        if missing:
            raise ValueError(f"session liquidity feature_csv missing columns: {sorted(missing)}")
        out = {}
        for row in df.to_dict("records"):
            session_date = pd.Timestamp(row["session_date"]).date()
            values = {name: _required_float(row.get(name), name) for name in required if name != "session_date"}
            if values["asia_high"] <= values["asia_low"] or values["london_high"] <= values["london_low"]:
                continue
            out[session_date] = values
        return out

    def _validate(self) -> None:
        allowed_modes = {
            "asia_high_failed_sweep_short",
            "asia_low_failed_sweep_long",
            "asia_two_sided_failed_sweep",
            "asia_high_fvg_rejection_short",
            "asia_low_fvg_rejection_long",
            "asia_two_sided_fvg_rejection",
            "london_high_fvg_rejection_short",
            "london_low_fvg_rejection_long",
            "london_two_sided_fvg_rejection",
            "combined_two_sided_fvg_rejection",
        }
        if self.setup_mode not in allowed_modes:
            raise ValueError(f"Unsupported setup_mode: {self.setup_mode}.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be positive.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be positive.")
        if self.sweep_buffer_ticks < 0 or self.reclaim_close_buffer_ticks < 0 or self.min_gap_ticks < 0:
            raise ValueError("tick parameters must be non-negative.")
        if self.max_reclaim_bars < 0 or self.max_fvg_retest_bars <= 0:
            raise ValueError("bar-window parameters are invalid.")


def _date(value) -> object:
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
        raise ValueError(f"entry bar or feature row is missing finite {name}.")
    return out
