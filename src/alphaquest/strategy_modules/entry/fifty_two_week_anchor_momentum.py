from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


@dataclass(frozen=True)
class _DailyStats:
    session_date: date
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class _AnchorState:
    anchor_high: float
    anchor_low: float
    prior_close: float
    prior_twenty_low: float
    high_session_date: date
    low_session_date: date
    nearness_to_high: float


class FiftyTwoWeekAnchorMomentumEntry:
    name = "fifty_two_week_anchor_momentum"

    def __init__(self, params: dict):
        self.params = dict(params)
        self.setup_mode = str(params.get("setup_mode", "near_high_opening_drive_long")).lower()
        self.start_time = parse_time(params.get("start_time", "09:45:00"))
        self.end_time = parse_time(params.get("end_time", "12:30:00"))
        self.rth_end = parse_time(params.get("rth_end", "16:00:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.lookback_sessions = int(params.get("lookback_sessions", 252))
        self.proximity_pct = float(params.get("proximity_pct", 0.02))
        self.far_from_high_pct = float(params.get("far_from_high_pct", 0.08))
        self.min_session_return_bps = float(params.get("min_session_return_bps", 10.0))
        self.breakout_buffer_ticks = float(params.get("breakout_buffer_ticks", 2.0))
        self.pullback_min_bps = float(params.get("pullback_min_bps", 15.0))
        self.hold_buffer_bps = float(params.get("hold_buffer_bps", 50.0))
        self.extension_min_bps = float(params.get("extension_min_bps", 10.0))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.state_by_day: dict[date, dict] = {}
        self.daily_stats: list[_DailyStats] = []
        self._anchor_cache: dict[date, _AnchorState | None] = {}
        self._validate()

    @property
    def _buffer(self) -> float:
        return self.tick_size * self.breakout_buffer_ticks

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _date(bar.get("session_date", timestamp.date()))
        state = self._state(session_date)
        self._update_intraday_state(bar, state)
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)

        signal = None
        if (
            not state["signaled"]
            and trades_today < self.max_trades_per_day
            and self.start_time <= bar_close.time() <= self.end_time
        ):
            signal = self._signal_for_mode(bar, bar_close, session_date, state)
            if signal is not None:
                state["signaled"] = True

        if not state["recorded_daily"] and bar_close.time() >= self.rth_end:
            self._record_daily_stats(session_date, state)
            state["recorded_daily"] = True
        return signal

    def _state(self, session_date: date) -> dict:
        return self.state_by_day.setdefault(
            session_date,
            {
                "signaled": False,
                "recorded_daily": False,
                "session_open": None,
                "session_high": None,
                "session_low": None,
                "session_close": None,
            },
        )

    def _update_intraday_state(self, bar: pd.Series, state: dict) -> None:
        open_ = _required_float(bar.get("open"), "open")
        high = _required_float(bar.get("high"), "high")
        low = _required_float(bar.get("low"), "low")
        close = _required_float(bar.get("close"), "close")
        if state["session_open"] is None:
            state["session_open"] = open_
        state["session_high"] = high if state["session_high"] is None else max(float(state["session_high"]), high)
        state["session_low"] = low if state["session_low"] is None else min(float(state["session_low"]), low)
        state["session_close"] = close

    def _record_daily_stats(self, session_date: date, state: dict) -> None:
        if any(value is None for value in (state["session_open"], state["session_high"], state["session_low"], state["session_close"])):
            return
        self.daily_stats.append(
            _DailyStats(
                session_date=session_date,
                open=float(state["session_open"]),
                high=float(state["session_high"]),
                low=float(state["session_low"]),
                close=float(state["session_close"]),
            )
        )

    def _signal_for_mode(
        self,
        bar: pd.Series,
        bar_close: pd.Timestamp,
        session_date: date,
        state: dict,
    ) -> Signal | None:
        anchor = self._anchor_state(session_date)
        if anchor is None:
            return None
        close = _required_float(bar.get("close"), "close")
        session_return_bps = self._session_return_bps(close, state)
        if session_return_bps is None:
            return None

        mode = self.setup_mode
        if mode == "near_high_opening_drive_long":
            if not self._is_near_high(anchor) or session_return_bps < self.min_session_return_bps:
                return None
            return self._signal(bar, bar_close, anchor, "long", anchor.prior_close, session_return_bps)

        if mode == "near_high_breakout_long":
            if not self._is_near_high(anchor) or close < anchor.anchor_high + self._buffer:
                return None
            return self._signal(bar, bar_close, anchor, "long", anchor.anchor_high, session_return_bps)

        if mode == "near_high_pullback_reclaim_long":
            session_low = _finite_float(state.get("session_low"))
            if session_low is None:
                return None
            pulled_back = session_low <= anchor.prior_close * (1.0 - self.pullback_min_bps / 10000.0)
            if (
                not self._is_near_high(anchor)
                or not pulled_back
                or close < anchor.prior_close + self._buffer
                or session_return_bps < self.min_session_return_bps
            ):
                return None
            return self._signal(bar, bar_close, anchor, "long", anchor.prior_close, session_return_bps)

        if mode == "near_high_anchor_hold_long":
            session_low = _finite_float(state.get("session_low"))
            if session_low is None:
                return None
            held_anchor = session_low >= anchor.prior_close * (1.0 - self.hold_buffer_bps / 10000.0)
            if not self._is_near_high(anchor) or not held_anchor or session_return_bps < self.min_session_return_bps:
                return None
            return self._signal(bar, bar_close, anchor, "long", anchor.prior_close, session_return_bps)

        if mode == "near_high_extension_hold_long":
            session_high = _finite_float(state.get("session_high"))
            if session_high is None:
                return None
            extended = session_high >= anchor.prior_close * (1.0 + self.extension_min_bps / 10000.0)
            if not self._is_near_high(anchor) or not extended or session_return_bps < self.min_session_return_bps:
                return None
            return self._signal(bar, bar_close, anchor, "long", anchor.prior_close, session_return_bps)

        if mode == "far_from_high_opening_drive_short":
            if not self._is_far_from_high(anchor) or session_return_bps > -self.min_session_return_bps:
                return None
            return self._signal(bar, bar_close, anchor, "short", anchor.prior_close, session_return_bps)

        if mode == "far_from_high_breakdown_short":
            if (
                not self._is_far_from_high(anchor)
                or close > anchor.prior_twenty_low - self._buffer
                or session_return_bps > -self.min_session_return_bps
            ):
                return None
            return self._signal(bar, bar_close, anchor, "short", anchor.prior_twenty_low, session_return_bps)

        raise ValueError(f"Unknown fifty_two_week_anchor_momentum setup_mode: {self.setup_mode}")

    def _anchor_state(self, session_date: date) -> _AnchorState | None:
        if session_date in self._anchor_cache:
            return self._anchor_cache[session_date]
        if self.daily_stats and self.daily_stats[-1].session_date < session_date:
            prior = self.daily_stats
        else:
            prior = [item for item in self.daily_stats if item.session_date < session_date]
        if len(prior) < self.lookback_sessions:
            self._anchor_cache[session_date] = None
            return None
        window = prior[-self.lookback_sessions :]
        anchor_high_day = max(window, key=lambda item: item.high)
        anchor_low_day = min(window, key=lambda item: item.low)
        prior_close = float(prior[-1].close)
        if prior_close <= 0 or anchor_high_day.high <= 0:
            self._anchor_cache[session_date] = None
            return None
        recent_twenty = prior[-min(20, len(prior)) :]
        anchor = _AnchorState(
            anchor_high=float(anchor_high_day.high),
            anchor_low=float(anchor_low_day.low),
            prior_close=prior_close,
            prior_twenty_low=min(float(item.low) for item in recent_twenty),
            high_session_date=anchor_high_day.session_date,
            low_session_date=anchor_low_day.session_date,
            nearness_to_high=prior_close / float(anchor_high_day.high),
        )
        self._anchor_cache[session_date] = anchor
        return anchor

    def _is_near_high(self, anchor: _AnchorState) -> bool:
        return anchor.nearness_to_high >= 1.0 - self.proximity_pct

    def _is_far_from_high(self, anchor: _AnchorState) -> bool:
        return anchor.nearness_to_high <= 1.0 - self.far_from_high_pct

    def _session_return_bps(self, close: float, state: dict) -> float | None:
        session_open = _finite_float(state.get("session_open"))
        if session_open is None or session_open <= 0:
            return None
        return (close / session_open - 1.0) * 10000.0

    def _signal(
        self,
        bar: pd.Series,
        bar_close: pd.Timestamp,
        anchor: _AnchorState,
        direction: str,
        swept_level: float,
        session_return_bps: float,
    ) -> Signal:
        high = _required_float(bar.get("high"), "high")
        low = _required_float(bar.get("low"), "low")
        close = _required_float(bar.get("close"), "close")
        report_fields = {
            "academic_source_key": "george_hwang_2004_52_week_high_momentum",
            "setup_mode": self.setup_mode,
            "lookback_sessions": self.lookback_sessions,
            "anchor_high": anchor.anchor_high,
            "anchor_low": anchor.anchor_low,
            "prior_close": anchor.prior_close,
            "prior_twenty_low": anchor.prior_twenty_low,
            "anchor_high_session_date": anchor.high_session_date.isoformat(),
            "anchor_low_session_date": anchor.low_session_date.isoformat(),
            "nearness_to_high": anchor.nearness_to_high,
            "proximity_pct": self.proximity_pct,
            "far_from_high_pct": self.far_from_high_pct,
            "min_session_return_bps": self.min_session_return_bps,
            "breakout_buffer_ticks": self.breakout_buffer_ticks,
            "pullback_min_bps": self.pullback_min_bps,
            "hold_buffer_bps": self.hold_buffer_bps,
            "extension_min_bps": self.extension_min_bps,
            "signal_close": close,
            "signal_session_return_bps": session_return_bps,
            "signal_timestamp": bar_close,
            "intended_entry_timestamp": bar_close,
        }
        return Signal(
            direction=direction,
            level_type=f"fifty_two_week_anchor_{self.setup_mode}",
            swept_level=float(swept_level),
            sweep_timestamp=bar_close,
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=bar_close,
            metadata={
                "setup_mode": self.setup_mode,
                "nearness_to_high": anchor.nearness_to_high,
                "anchor_high": anchor.anchor_high,
                "prior_close": anchor.prior_close,
            },
            report_fields=report_fields,
        )

    def _validate(self) -> None:
        if self.setup_mode not in {
            "near_high_opening_drive_long",
            "near_high_breakout_long",
            "near_high_pullback_reclaim_long",
            "near_high_anchor_hold_long",
            "near_high_extension_hold_long",
            "far_from_high_opening_drive_short",
            "far_from_high_breakdown_short",
        }:
            raise ValueError("entry.params.setup_mode is unsupported for fifty_two_week_anchor_momentum.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than zero.")
        if self.lookback_sessions < 20:
            raise ValueError("entry.params.lookback_sessions must be at least 20.")
        if not 0 < self.proximity_pct < 1:
            raise ValueError("entry.params.proximity_pct must be in (0, 1).")
        if not 0 < self.far_from_high_pct < 1:
            raise ValueError("entry.params.far_from_high_pct must be in (0, 1).")
        if (
            self.tick_size <= 0
            or self.breakout_buffer_ticks < 0
            or self.pullback_min_bps < 0
            or self.hold_buffer_bps < 0
            or self.extension_min_bps < 0
        ):
            raise ValueError("tick_size must be positive and buffer/hold/pullback thresholds must be non-negative.")
        if self.max_trades_per_day <= 0:
            raise ValueError("entry.params.max_trades_per_day must be greater than zero.")


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


def _required_float(value, field_name: str) -> float:
    out = _finite_float(value)
    if out is None:
        raise ValueError(f"bar field {field_name} must be finite.")
    return out
