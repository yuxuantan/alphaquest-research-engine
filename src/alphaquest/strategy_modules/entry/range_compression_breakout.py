from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class RangeCompressionBreakoutEntry:
    name = "range_compression_breakout"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "nr_breakout")).lower()
        self.rth_start = parse_time(params.get("rth_start", "09:30:00"))
        self.start_time = parse_time(params.get("start_time", "09:35:00"))
        self.end_time = parse_time(params.get("end_time", "13:30:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.opening_range_minutes = float(params.get("opening_range_minutes", 15))
        self.lookback_days = int(params.get("lookback_days", 4))
        self.max_range_rank_pct = params.get("max_range_rank_pct")
        self.require_inside_day = bool(
            params.get("require_inside_day", self.setup_mode in {"id_nr4", "id_nr4_breakout", "inside_nr_breakout"})
        )
        self.breakout_level_source = str(params.get("breakout_level_source", "prior_session")).lower()
        self.min_prior_range_points = params.get("min_prior_range_points")
        self.max_prior_range_points = params.get("max_prior_range_points")
        self.min_breakout_ticks = float(params.get("min_breakout_ticks", 0))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.require_open_inside_reference = bool(params.get("require_open_inside_reference", False))
        self.state_by_day: dict = {}
        self.session_stats: dict = {}

        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.opening_range_minutes <= 0:
            raise ValueError("opening_range_minutes must be greater than 0.")
        if self.lookback_days <= 0:
            raise ValueError("lookback_days must be greater than 0.")
        if self.breakout_level_source not in {"prior_session", "opening_range"}:
            raise ValueError("breakout_level_source must be prior_session or opening_range.")

    def _state(self, session_date):
        return self.state_by_day.setdefault(
            session_date,
            {
                "signaled": False,
                "opening_bars": [],
                "opening_range": None,
                "session_open": None,
            },
        )

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        session_date = pd.Timestamp(bar["session_date"]).date()
        state = self._state(session_date)
        if state["session_open"] is None:
            state["session_open"] = _finite_float(bar.get("open"))

        self._update_opening_range(bar, state, timestamp)
        self._update_session_stats(bar, session_date)

        if trades_today >= self.max_trades_per_day or state["signaled"]:
            return None
        if bar_close.time() < self.start_time or bar_close.time() > self.end_time:
            return None

        setup = self._setup_for_session(session_date)
        if setup is None:
            return None

        reference = self._breakout_reference(state, setup)
        if reference is None:
            return None
        if self.require_open_inside_reference and not _inside_reference(state.get("session_open"), reference):
            return None

        signal = self._signal_from_breakout(bar, bar_close, setup, reference)
        if signal is not None:
            state["signaled"] = True
        return signal

    def _update_session_stats(self, bar: pd.Series, session_date) -> None:
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
                "first_timestamp": bar["timestamp"],
                "last_timestamp": bar["timestamp"],
            }
            return
        stats["high"] = max(float(stats["high"]), high)
        stats["low"] = min(float(stats["low"]), low)
        stats["close"] = close
        stats["last_timestamp"] = bar["timestamp"]

    def _update_opening_range(self, bar: pd.Series, state: dict, timestamp: pd.Timestamp) -> None:
        if self.breakout_level_source != "opening_range" or state["opening_range"] is not None:
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
        opens = [_finite_float(bars[0].get("open"))]
        if any(value is None for value in [*highs, *lows, *opens]):
            return None
        return {
            "source": "opening_range",
            "high": max(highs),
            "low": min(lows),
            "open": opens[0],
            "start_timestamp": bars[0]["timestamp"],
            "end_timestamp": pd.Timestamp(bars[-1]["timestamp"]) + pd.Timedelta(minutes=self.bar_interval_minutes),
        }

    def _setup_for_session(self, session_date) -> dict | None:
        history = [self.session_stats[key] for key in sorted(self.session_stats) if key < session_date]
        if len(history) < self.lookback_days:
            return None
        prior = history[-1]
        prior_range = _session_range(prior)
        if prior_range is None:
            return None
        if self.min_prior_range_points is not None and prior_range < float(self.min_prior_range_points):
            return None
        if self.max_prior_range_points is not None and prior_range > float(self.max_prior_range_points):
            return None

        window = history[-self.lookback_days :]
        ranges = [_session_range(item) for item in window]
        if any(value is None for value in ranges):
            return None
        rank_pct = sum(1 for value in ranges if value <= prior_range) / len(ranges)
        max_rank = float(self.max_range_rank_pct) if self.max_range_rank_pct is not None else (1.0 / self.lookback_days)
        if rank_pct > max_rank + 1e-12:
            return None

        inside_day = False
        if len(history) >= 2:
            previous = history[-2]
            inside_day = float(prior["high"]) <= float(previous["high"]) and float(prior["low"]) >= float(previous["low"])
        if self.require_inside_day and not inside_day:
            return None

        return {
            "prior": prior,
            "prior_range": prior_range,
            "range_rank_pct": rank_pct,
            "lookback_days": self.lookback_days,
            "inside_day": inside_day,
        }

    def _breakout_reference(self, state: dict, setup: dict) -> dict | None:
        if self.breakout_level_source == "opening_range":
            return state.get("opening_range")
        prior = setup["prior"]
        return {
            "source": "prior_session",
            "high": float(prior["high"]),
            "low": float(prior["low"]),
            "open": float(prior["open"]),
            "start_timestamp": prior.get("first_timestamp"),
            "end_timestamp": prior.get("last_timestamp"),
        }

    def _signal_from_breakout(
        self,
        bar: pd.Series,
        bar_close: pd.Timestamp,
        setup: dict,
        reference: dict,
    ) -> Signal | None:
        close = _finite_float(bar.get("close"))
        high = _finite_float(reference.get("high"))
        low = _finite_float(reference.get("low"))
        if close is None or high is None or low is None:
            return None
        buffer = self.min_breakout_ticks * self.tick_size
        direction = None
        breakout_level = None
        if self.allow_long and close >= high + buffer:
            direction = "long"
            breakout_level = high
        elif self.allow_short and close <= low - buffer:
            direction = "short"
            breakout_level = low
        if direction is None:
            return None

        confirmation_high = _finite_float(bar.get("high"))
        confirmation_low = _finite_float(bar.get("low"))
        report_fields = {
            "academic_source_key": "crabel_raschke_connors_nr_breakout",
            "setup_mode": self.setup_mode,
            "range_compression_lookback_days": setup["lookback_days"],
            "prior_session_range": setup["prior_range"],
            "prior_session_range_rank_pct": setup["range_rank_pct"],
            "prior_session_inside_day": setup["inside_day"],
            "breakout_level_source": reference["source"],
            "breakout_level": breakout_level,
            "breakout_timestamp": bar_close,
            "reference_high": high,
            "reference_low": low,
            "confirmation_close": close,
            "confirmation_high": confirmation_high,
            "confirmation_low": confirmation_low,
        }
        return Signal(
            direction=direction,
            level_type=f"range_compression_{self.setup_mode}_{reference['source']}_{direction}",
            swept_level=breakout_level,
            sweep_timestamp=reference.get("start_timestamp") or bar["timestamp"],
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=bar_close,
            metadata={
                "confirmation_close": close,
                "confirmation_high": confirmation_high,
                "confirmation_low": confirmation_low,
                "breakout_timestamp": bar_close,
            },
            report_fields=report_fields,
        )

    def _elapsed_minutes(self, timestamp: pd.Timestamp) -> float:
        start = timestamp.replace(
            hour=self.rth_start.hour,
            minute=self.rth_start.minute,
            second=self.rth_start.second,
            microsecond=0,
        )
        return (timestamp - start).total_seconds() / 60.0


def _session_range(stats: dict) -> float | None:
    high = _finite_float(stats.get("high"))
    low = _finite_float(stats.get("low"))
    if high is None or low is None:
        return None
    out = high - low
    return out if math.isfinite(out) and out >= 0 else None


def _inside_reference(open_price, reference: dict) -> bool:
    open_ = _finite_float(open_price)
    high = _finite_float(reference.get("high"))
    low = _finite_float(reference.get("low"))
    if open_ is None or high is None or low is None:
        return False
    return low <= open_ <= high


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
