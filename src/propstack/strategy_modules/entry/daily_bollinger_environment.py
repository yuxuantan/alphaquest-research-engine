from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import math
from statistics import fmean, pstdev

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


@dataclass(frozen=True)
class _DailyBollingerState:
    session_date: date
    open: float
    high: float
    low: float
    close: float
    middle: float
    upper: float
    lower: float
    width: float
    width_rank: float


class DailyBollingerEnvironmentEntry:
    name = "daily_bollinger_environment"

    def __init__(self, params: dict):
        self.params = dict(params)
        self.setup_mode = str(params.get("setup_mode", "expansion_long_breakout")).lower()
        self.rth_start = parse_time(params.get("rth_start", "09:30:00"))
        self.start_time = parse_time(params.get("start_time", "09:45:00"))
        self.end_time = parse_time(params.get("end_time", "11:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.opening_range_minutes = float(params.get("opening_range_minutes", 15))
        self.bb_length = int(params.get("bb_length", 20))
        self.bb_std = float(params.get("bb_std", 3.0))
        self.width_rank_lookback = int(params.get("width_rank_lookback", 60))
        self.width_rank_threshold = float(params.get("width_rank_threshold", 0.65))
        self.mean_reversion_peak_lookback = int(params.get("mean_reversion_peak_lookback", 10))
        self.mean_reversion_trigger_fraction = float(params.get("mean_reversion_trigger_fraction", 0.30))
        self.min_breakout_ticks = float(params.get("min_breakout_ticks", 0.0))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.state_by_day: dict[date, dict] = {}
        self.session_stats: dict[date, dict] = {}
        self._daily_states: list[_DailyBollingerState] = []
        self._processed_state_dates: set[date] = set()
        self._setup_cache: dict[date, dict | None] = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _date(bar.get("session_date", timestamp.date()))
        state = self._state(session_date)
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)

        try:
            self._update_opening_range(bar, state, timestamp)
            if state["signaled"] or trades_today >= self.max_trades_per_day:
                return None
            if bar_close.time() < self.start_time or bar_close.time() > self.end_time:
                return None

            setup = self._setup_for_session(session_date)
            if setup is None:
                return None

            signal = self._signal_for_setup(bar, bar_close, setup, state)
            if signal is not None:
                state["signaled"] = True
            return signal
        finally:
            self._record_session_bar(bar, session_date)

    def _setup_for_session(self, session_date: date) -> dict | None:
        if session_date in self._setup_cache:
            return self._setup_cache[session_date]

        self._ensure_daily_states_before(session_date)
        states = [state for state in self._daily_states if state.session_date < session_date]
        if len(states) < 2:
            self._setup_cache[session_date] = None
            return None
        current = states[-1]
        previous = states[-2]
        recent = states[-self.mean_reversion_peak_lookback :]
        mode = self.setup_mode

        if mode == "expansion_long_breakout":
            if current.width <= previous.width or current.width_rank < self.width_rank_threshold:
                self._setup_cache[session_date] = None
                return None
            if current.high < current.upper or current.close <= current.middle:
                self._setup_cache[session_date] = None
                return None
            setup = {"environment": "expansion_long", "current": current, "previous": previous, "recent": recent}
            self._setup_cache[session_date] = setup
            return setup

        if mode == "expansion_short_breakout":
            if current.width <= previous.width or current.width_rank < self.width_rank_threshold:
                self._setup_cache[session_date] = None
                return None
            if current.low > current.lower or current.close >= current.middle:
                self._setup_cache[session_date] = None
                return None
            setup = {"environment": "expansion_short", "current": current, "previous": previous, "recent": recent}
            self._setup_cache[session_date] = setup
            return setup

        if mode == "consolidation_edge_reversion":
            if current.width >= previous.width or current.width_rank > self.width_rank_threshold:
                self._setup_cache[session_date] = None
                return None
            if not (current.lower <= current.close <= current.upper):
                self._setup_cache[session_date] = None
                return None
            setup = {"environment": "consolidation", "current": current, "previous": previous, "recent": recent}
            self._setup_cache[session_date] = setup
            return setup

        if mode == "mean_reversion_short":
            if current.width >= previous.width or current.width_rank < self.width_rank_threshold:
                self._setup_cache[session_date] = None
                return None
            upper_peak = max(item.upper for item in recent)
            trigger = upper_peak - self.mean_reversion_trigger_fraction * (upper_peak - current.middle)
            if not any(item.high >= item.upper for item in recent):
                self._setup_cache[session_date] = None
                return None
            if current.close > trigger:
                self._setup_cache[session_date] = None
                return None
            setup = {
                "environment": "mean_reversion_short",
                "current": current,
                "previous": previous,
                "recent": recent,
                "mean_reversion_trigger": trigger,
            }
            self._setup_cache[session_date] = setup
            return setup

        if mode == "mean_reversion_long":
            if current.width >= previous.width or current.width_rank < self.width_rank_threshold:
                self._setup_cache[session_date] = None
                return None
            lower_peak = min(item.lower for item in recent)
            trigger = lower_peak + self.mean_reversion_trigger_fraction * (current.middle - lower_peak)
            if not any(item.low <= item.lower for item in recent):
                self._setup_cache[session_date] = None
                return None
            if current.close < trigger:
                self._setup_cache[session_date] = None
                return None
            setup = {
                "environment": "mean_reversion_long",
                "current": current,
                "previous": previous,
                "recent": recent,
                "mean_reversion_trigger": trigger,
            }
            self._setup_cache[session_date] = setup
            return setup

        raise ValueError(f"Unknown daily_bollinger_environment setup_mode: {self.setup_mode}")

    def _signal_for_setup(
        self,
        bar: pd.Series,
        bar_close: pd.Timestamp,
        setup: dict,
        state: dict,
    ) -> Signal | None:
        environment = setup["environment"]
        if environment in {"expansion_long", "mean_reversion_long"}:
            return self._opening_range_breakout_signal(bar, bar_close, setup, state, "long")
        if environment in {"expansion_short", "mean_reversion_short"}:
            return self._opening_range_breakout_signal(bar, bar_close, setup, state, "short")
        if environment == "consolidation":
            return self._consolidation_edge_signal(bar, bar_close, setup)
        return None

    def _opening_range_breakout_signal(
        self,
        bar: pd.Series,
        bar_close: pd.Timestamp,
        setup: dict,
        state: dict,
        direction: str,
    ) -> Signal | None:
        opening_range = state.get("opening_range")
        if opening_range is None:
            return None
        close = _required_float(bar.get("close"), "close")
        buffer = self.min_breakout_ticks * self.tick_size
        if direction == "long":
            level = float(opening_range["high"])
            if close < level + buffer:
                return None
            level_type = f"daily_bb_{setup['environment']}_or_breakout"
        else:
            level = float(opening_range["low"])
            if close > level - buffer:
                return None
            level_type = f"daily_bb_{setup['environment']}_or_breakout"
        return self._signal(bar, bar_close, setup, direction, level_type, level)

    def _consolidation_edge_signal(self, bar: pd.Series, bar_close: pd.Timestamp, setup: dict) -> Signal | None:
        current: _DailyBollingerState = setup["current"]
        close = _required_float(bar.get("close"), "close")
        high = _required_float(bar.get("high"), "high")
        low = _required_float(bar.get("low"), "low")
        buffer = self.min_breakout_ticks * self.tick_size
        if high >= current.high + buffer and close < current.high:
            return self._signal(
                bar,
                bar_close,
                setup,
                "short",
                "daily_bb_consolidation_prior_high_rejection",
                current.high,
            )
        if low <= current.low - buffer and close > current.low:
            return self._signal(
                bar,
                bar_close,
                setup,
                "long",
                "daily_bb_consolidation_prior_low_reclaim",
                current.low,
            )
        return None

    def _signal(
        self,
        bar: pd.Series,
        bar_close: pd.Timestamp,
        setup: dict,
        direction: str,
        level_type: str,
        swept_level: float,
    ) -> Signal:
        high = _required_float(bar.get("high"), "high")
        low = _required_float(bar.get("low"), "low")
        close = _required_float(bar.get("close"), "close")
        current: _DailyBollingerState = setup["current"]
        report_fields = {
            "setup_mode": self.setup_mode,
            "daily_bb_environment": setup["environment"],
            "bb_length": self.bb_length,
            "bb_std": self.bb_std,
            "bb_state_session_date": current.session_date.isoformat(),
            "bb_middle": current.middle,
            "bb_upper": current.upper,
            "bb_lower": current.lower,
            "bb_width": current.width,
            "bb_width_rank": current.width_rank,
            "width_rank_threshold": self.width_rank_threshold,
            "signal_close": close,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        if "mean_reversion_trigger" in setup:
            report_fields["mean_reversion_trigger"] = setup["mean_reversion_trigger"]
        return Signal(
            direction=direction,
            level_type=level_type,
            swept_level=swept_level,
            sweep_timestamp=bar_close,
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=bar_close,
            metadata={
                "setup_mode": self.setup_mode,
                "daily_bb_environment": setup["environment"],
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _ensure_daily_states_before(self, session_date: date) -> None:
        ordered_dates = sorted(day for day in self.session_stats if day < session_date)
        for idx, day in enumerate(ordered_dates):
            if day in self._processed_state_dates:
                continue
            if idx + 1 < self.bb_length:
                continue
            window = [self.session_stats[item] for item in ordered_dates[idx - self.bb_length + 1 : idx + 1]]
            closes = [_required_float(item.get("close"), "close") for item in window]
            middle = fmean(closes)
            std = pstdev(closes)
            upper = middle + self.bb_std * std
            lower = middle - self.bb_std * std
            width = upper - lower
            rank_window = self._daily_states[-self.width_rank_lookback + 1 :] if self.width_rank_lookback > 1 else []
            rank_values = [state.width for state in rank_window] + [width]
            width_rank = sum(1 for value in rank_values if value <= width) / len(rank_values)
            current = self.session_stats[day]
            self._daily_states.append(
                _DailyBollingerState(
                    session_date=day,
                    open=_required_float(current.get("open"), "open"),
                    high=_required_float(current.get("high"), "high"),
                    low=_required_float(current.get("low"), "low"),
                    close=_required_float(current.get("close"), "close"),
                    middle=middle,
                    upper=upper,
                    lower=lower,
                    width=width,
                    width_rank=width_rank,
                )
            )
            self._processed_state_dates.add(day)

    def _update_opening_range(self, bar: pd.Series, state: dict, timestamp: pd.Timestamp) -> None:
        if state["opening_range"] is not None:
            return
        elapsed = self._elapsed_minutes(timestamp)
        if elapsed < 0:
            return
        if elapsed < self.opening_range_minutes:
            state["opening_bars"].append(bar)
            if self._opening_bars_complete(state["opening_bars"]):
                state["opening_range"] = self._build_opening_range(state["opening_bars"])
            return
        if state["opening_bars"]:
            state["opening_range"] = self._build_opening_range(state["opening_bars"])

    def _opening_bars_complete(self, bars: list[pd.Series]) -> bool:
        required = max(1, int(math.ceil(self.opening_range_minutes / self.bar_interval_minutes)))
        return len(bars) >= required

    def _build_opening_range(self, bars: list[pd.Series]) -> dict | None:
        if not bars:
            return None
        highs = [_finite_float(bar.get("high")) for bar in bars]
        lows = [_finite_float(bar.get("low")) for bar in bars]
        if any(value is None for value in [*highs, *lows]):
            return None
        return {
            "high": max(highs),
            "low": min(lows),
            "start_timestamp": bars[0]["timestamp"],
            "end_timestamp": pd.Timestamp(bars[-1]["timestamp"]) + pd.Timedelta(minutes=self.bar_interval_minutes),
        }

    def _record_session_bar(self, bar: pd.Series, session_date: date) -> None:
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        close = _finite_float(bar.get("close"))
        open_ = _finite_float(bar.get("open"))
        if high is None or low is None or close is None or open_ is None:
            return
        stats = self.session_stats.get(session_date)
        if stats is None:
            self.session_stats[session_date] = {
                "session_date": session_date,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
            }
            return
        stats["high"] = max(float(stats["high"]), high)
        stats["low"] = min(float(stats["low"]), low)
        stats["close"] = close

    def _elapsed_minutes(self, timestamp: pd.Timestamp) -> float:
        start = pd.Timestamp(datetime.combine(timestamp.date(), self.rth_start))
        if timestamp.tzinfo is not None:
            start = start.tz_localize(timestamp.tzinfo)
        return (timestamp - start).total_seconds() / 60.0

    def _state(self, session_date: date) -> dict:
        return self.state_by_day.setdefault(
            session_date,
            {
                "signaled": False,
                "opening_bars": [],
                "opening_range": None,
            },
        )

    def _validate(self) -> None:
        allowed_modes = {
            "expansion_long_breakout",
            "expansion_short_breakout",
            "consolidation_edge_reversion",
            "mean_reversion_short",
            "mean_reversion_long",
        }
        if self.setup_mode not in allowed_modes:
            raise ValueError(f"setup_mode must be one of {sorted(allowed_modes)}.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.bar_interval_minutes <= 0 or self.opening_range_minutes <= 0:
            raise ValueError("bar_interval_minutes and opening_range_minutes must be greater than 0.")
        if self.bb_length < 3:
            raise ValueError("bb_length must be at least 3.")
        if self.bb_std <= 0 or not math.isfinite(self.bb_std):
            raise ValueError("bb_std must be positive and finite.")
        if self.width_rank_lookback < 1:
            raise ValueError("width_rank_lookback must be positive.")
        if not 0 <= self.width_rank_threshold <= 1:
            raise ValueError("width_rank_threshold must be in [0, 1].")
        if self.mean_reversion_peak_lookback < 2:
            raise ValueError("mean_reversion_peak_lookback must be at least 2.")
        if not 0 < self.mean_reversion_trigger_fraction < 1:
            raise ValueError("mean_reversion_trigger_fraction must be in (0, 1).")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")


def _date(value) -> date:
    if isinstance(value, date):
        return value
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
