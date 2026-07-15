from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd


@dataclass(frozen=True)
class StructureState:
    direction: str | None
    timeframe_minutes: int
    pattern: str
    pivots: tuple[dict, ...]


class MultiTimeframePivotStructure:
    """Completed swing-pivot market-structure state.

    Bars are aggregated from the strategy timeframe into fixed RTH-anchored
    buckets. A pivot is usable only after the configured right-side confirmation
    bars are complete.
    """

    def __init__(
        self,
        *,
        timeframes_minutes: list[int],
        bar_interval_minutes: float,
        rth_start,
        tick_size: float = 0.25,
        pivot_left_bars: int = 1,
        pivot_right_bars: int = 1,
        min_pivot_move_ticks: float = 0.0,
        min_aligned_timeframes: int | None = None,
        carry_pivots_across_sessions: bool = False,
    ):
        if bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if pivot_left_bars <= 0 or pivot_right_bars <= 0:
            raise ValueError("pivot_left_bars and pivot_right_bars must be positive.")
        timeframes = [int(value) for value in timeframes_minutes]
        if not timeframes:
            raise ValueError("timeframes_minutes must contain at least one timeframe.")
        for minutes in timeframes:
            if minutes <= 0:
                raise ValueError("timeframes_minutes values must be positive.")
            ratio = minutes / float(bar_interval_minutes)
            if not math.isclose(ratio, round(ratio)):
                raise ValueError("Each structure timeframe must be a multiple of bar_interval_minutes.")
        self.timeframes_minutes = tuple(sorted(set(timeframes)))
        self.bar_interval_minutes = float(bar_interval_minutes)
        self.rth_start = rth_start
        self.tick_size = float(tick_size)
        self.pivot_left_bars = int(pivot_left_bars)
        self.pivot_right_bars = int(pivot_right_bars)
        self.min_pivot_move = float(min_pivot_move_ticks) * self.tick_size
        self.min_pivot_move_ticks = float(min_pivot_move_ticks)
        self.min_aligned_timeframes = int(min_aligned_timeframes or len(self.timeframes_minutes))
        if self.min_aligned_timeframes <= 0 or self.min_aligned_timeframes > len(self.timeframes_minutes):
            raise ValueError("min_aligned_timeframes must be between 1 and the number of timeframes.")
        self.carry_pivots_across_sessions = bool(carry_pivots_across_sessions)
        self.state_by_day: dict = {}
        self._anchor_cache: dict = {}

    def update(self, bar: pd.Series) -> None:
        if not bool(bar.get("is_rth", False)):
            return
        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = bar.get("session_date", timestamp.date())
        state = self._day_state(session_date)
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        for minutes in self.timeframes_minutes:
            self._update_timeframe(state[minutes], bar, timestamp, bar_close, minutes)

    def bias(self) -> dict:
        states = [self._timeframe_state(tf_state, minutes) for minutes, tf_state in self._active_tf_states()]
        long_states = [state for state in states if state.direction == "long"]
        short_states = [state for state in states if state.direction == "short"]
        if len(long_states) >= self.min_aligned_timeframes and len(short_states) == 0:
            direction = "long"
        elif len(short_states) >= self.min_aligned_timeframes and len(long_states) == 0:
            direction = "short"
        else:
            direction = None
        return {
            "direction": direction,
            "aligned_count": len(long_states) if direction == "long" else len(short_states) if direction == "short" else 0,
            "states": states,
        }

    def report_fields(self, prefix: str = "market_structure") -> dict:
        bias = self.bias()
        out = {
            f"{prefix}_direction": bias["direction"] or "none",
            f"{prefix}_aligned_count": bias["aligned_count"],
            f"{prefix}_required_aligned_count": self.min_aligned_timeframes,
            f"{prefix}_timeframes_minutes": ",".join(str(value) for value in self.timeframes_minutes),
            f"{prefix}_pivot_left_bars": self.pivot_left_bars,
            f"{prefix}_pivot_right_bars": self.pivot_right_bars,
            f"{prefix}_min_pivot_move_ticks": self.min_pivot_move_ticks,
            f"{prefix}_carry_pivots_across_sessions": self.carry_pivots_across_sessions,
        }
        for state in bias["states"]:
            tf_prefix = f"{prefix}_{state.timeframe_minutes}m"
            out[f"{tf_prefix}_direction"] = state.direction or "none"
            out[f"{tf_prefix}_pattern"] = state.pattern
            for idx, pivot in enumerate(state.pivots[-4:], start=1):
                out[f"{tf_prefix}_pivot{idx}_type"] = pivot["type"]
                out[f"{tf_prefix}_pivot{idx}_price"] = pivot["price"]
                out[f"{tf_prefix}_pivot{idx}_timestamp"] = pivot["timestamp"]
        return out

    def _day_state(self, session_date) -> dict:
        if session_date in self.state_by_day:
            return self.state_by_day[session_date]
        prior_state = None
        if self.carry_pivots_across_sessions and self.state_by_day:
            prior_state = next(reversed(self.state_by_day.values()))
        state = {}
        for minutes in self.timeframes_minutes:
            carried_pivots = []
            if prior_state is not None:
                carried_pivots = [dict(item) for item in prior_state[minutes].get("pivots", [])[-12:]]
            state[minutes] = {"current": None, "bars": [], "pivots": carried_pivots}
        self.state_by_day[session_date] = state
        return state

    def _active_tf_states(self):
        if not self.state_by_day:
            return []
        latest_key = next(reversed(self.state_by_day))
        return self.state_by_day[latest_key].items()

    def _update_timeframe(
        self,
        tf_state: dict,
        bar: pd.Series,
        timestamp: pd.Timestamp,
        bar_close: pd.Timestamp,
        minutes: int,
    ) -> None:
        bucket_start = self._bucket_start(timestamp, bar.get("session_date"), minutes)
        current = tf_state.get("current")
        if current is not None and current["timestamp"] != bucket_start:
            self._finalize_current(tf_state)
            current = None
        if current is None:
            current = {
                "timestamp": bucket_start,
                "open": _required_float(bar.get("open"), "open"),
                "high": _required_float(bar.get("high"), "high"),
                "low": _required_float(bar.get("low"), "low"),
                "close": _required_float(bar.get("close"), "close"),
                "volume": _finite_float(bar.get("volume")) or 0.0,
            }
            tf_state["current"] = current
        else:
            current["high"] = max(current["high"], _required_float(bar.get("high"), "high"))
            current["low"] = min(current["low"], _required_float(bar.get("low"), "low"))
            current["close"] = _required_float(bar.get("close"), "close")
            current["volume"] += _finite_float(bar.get("volume")) or 0.0

        if bar_close >= bucket_start + pd.Timedelta(minutes=minutes):
            self._finalize_current(tf_state)
            tf_state["current"] = None

    def _finalize_current(self, tf_state: dict) -> None:
        current = tf_state.get("current")
        if current is None:
            return
        tf_state["bars"].append(dict(current))
        tf_state["bars"] = tf_state["bars"][-80:]
        self._confirm_new_pivots(tf_state)

    def _confirm_new_pivots(self, tf_state: dict) -> None:
        bars = tf_state["bars"]
        candidate_idx = len(bars) - self.pivot_right_bars - 1
        if candidate_idx < self.pivot_left_bars:
            return
        candidate = bars[candidate_idx]
        left = bars[candidate_idx - self.pivot_left_bars : candidate_idx]
        right = bars[candidate_idx + 1 : candidate_idx + 1 + self.pivot_right_bars]
        if len(right) < self.pivot_right_bars:
            return

        if candidate["high"] > max(item["high"] for item in left + right):
            self._append_pivot(
                tf_state,
                {
                    "type": "high",
                    "price": float(candidate["high"]),
                    "timestamp": candidate["timestamp"],
                },
            )
        if candidate["low"] < min(item["low"] for item in left + right):
            self._append_pivot(
                tf_state,
                {
                    "type": "low",
                    "price": float(candidate["low"]),
                    "timestamp": candidate["timestamp"],
                },
            )

    def _append_pivot(self, tf_state: dict, pivot: dict) -> None:
        pivots = tf_state["pivots"]
        if pivots and pivots[-1]["type"] == pivot["type"]:
            if pivot["type"] == "high" and pivot["price"] > pivots[-1]["price"]:
                pivots[-1] = pivot
            elif pivot["type"] == "low" and pivot["price"] < pivots[-1]["price"]:
                pivots[-1] = pivot
            return
        pivots.append(pivot)
        tf_state["pivots"] = pivots[-12:]

    def _timeframe_state(self, tf_state: dict, minutes: int) -> StructureState:
        pivots = tuple(tf_state.get("pivots", [])[-4:])
        if len(pivots) < 4:
            return StructureState(None, minutes, "insufficient_pivots", pivots)
        types = [pivot["type"] for pivot in pivots]
        if types not in (["high", "low", "high", "low"], ["low", "high", "low", "high"]):
            return StructureState(None, minutes, "non_alternating", pivots)
        highs = [pivot for pivot in pivots if pivot["type"] == "high"]
        lows = [pivot for pivot in pivots if pivot["type"] == "low"]
        higher_high = highs[1]["price"] >= highs[0]["price"] + self.min_pivot_move
        higher_low = lows[1]["price"] >= lows[0]["price"] + self.min_pivot_move
        lower_high = highs[1]["price"] <= highs[0]["price"] - self.min_pivot_move
        lower_low = lows[1]["price"] <= lows[0]["price"] - self.min_pivot_move
        if higher_high and higher_low:
            return StructureState("long", minutes, "HH_HL", pivots)
        if lower_high and lower_low:
            return StructureState("short", minutes, "LH_LL", pivots)
        return StructureState(None, minutes, "mixed", pivots)

    def _bucket_start(self, timestamp: pd.Timestamp, session_date, minutes: int) -> pd.Timestamp:
        cache_key = (pd.Timestamp(session_date).date(), str(timestamp.tz))
        anchor = self._anchor_cache.get(cache_key)
        if anchor is None:
            anchor = pd.Timestamp.combine(pd.Timestamp(session_date).date(), self.rth_start)
            if timestamp.tzinfo is not None:
                anchor = anchor.tz_localize(timestamp.tz)
            self._anchor_cache[cache_key] = anchor
        elapsed = timestamp - anchor
        bucket_number = int(elapsed.total_seconds() // (minutes * 60))
        return anchor + pd.Timedelta(minutes=bucket_number * minutes)


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
        raise ValueError(f"bar is missing finite {name}.")
    return out
