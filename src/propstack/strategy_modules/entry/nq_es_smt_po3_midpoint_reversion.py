from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class NqEsSmtPo3MidpointReversionEntry:
    name = "nq_es_smt_po3_midpoint_reversion"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "prior_two_sided")).lower()
        self.setup_start_time = parse_time(params.get("setup_start_time", "09:30:00"))
        self.start_time = parse_time(params.get("start_time", "10:00:00"))
        self.end_time = parse_time(params.get("end_time", "11:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.sweep_buffer_ticks = int(params.get("sweep_buffer_ticks", 0))
        self.reclaim_buffer_ticks = int(params.get("reclaim_buffer_ticks", 0))
        self.min_prior_range_ticks = float(params.get("min_prior_range_ticks", 20.0))
        self._session_date = None
        self._previous = None
        self._current = None
        self._state = self._new_state()
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _session_date(bar, timestamp)
        if session_date != self._session_date:
            self._roll_session(session_date)

        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        self._record_manipulation(bar, timestamp, bar_close)
        signal = self._maybe_signal(bar, timestamp, bar_close, trades_today)
        self._finish_bar(bar)
        return signal

    def _roll_session(self, session_date) -> None:
        if self._current and _finite(self._current["nq_high"]) and _finite(self._current["es_high"]):
            self._previous = dict(self._current)
        self._session_date = session_date
        self._current = {
            "nq_high": None,
            "nq_low": None,
            "es_high": None,
            "es_low": None,
        }
        self._state = self._new_state()

    def _record_manipulation(self, bar: pd.Series, timestamp: pd.Timestamp, bar_close: pd.Timestamp) -> None:
        if self._previous is None:
            return
        if bar_close.time() < self.setup_start_time or bar_close.time() > self.end_time:
            return
        if not self._prior_range_ok():
            return

        sweep_buffer = self.sweep_buffer_ticks * self.tick_size
        nq_high = float(bar["high"])
        nq_low = float(bar["low"])
        es_high = _finite_float(bar.get("es_high"))
        es_low = _finite_float(bar.get("es_low"))

        if self._allows_short():
            short = self._state["short"]
            es_confirmed = es_high is not None and es_high >= float(self._previous["es_high"]) + sweep_buffer
            if short["swept"] and es_confirmed:
                short["invalidated"] = True
            if (
                not short["swept"]
                and nq_high >= float(self._previous["nq_high"]) + sweep_buffer
                and not es_confirmed
            ):
                short.update(
                    {
                        "swept": True,
                        "sweep_timestamp": timestamp,
                        "protected_extreme": nq_high,
                        "smt_reference": float(self._previous["es_high"]),
                    }
                )
            elif short["swept"] and not short["invalidated"]:
                short["protected_extreme"] = max(float(short["protected_extreme"]), nq_high)

        if self._allows_long():
            long = self._state["long"]
            es_confirmed = es_low is not None and es_low <= float(self._previous["es_low"]) - sweep_buffer
            if long["swept"] and es_confirmed:
                long["invalidated"] = True
            if (
                not long["swept"]
                and nq_low <= float(self._previous["nq_low"]) - sweep_buffer
                and not es_confirmed
            ):
                long.update(
                    {
                        "swept": True,
                        "sweep_timestamp": timestamp,
                        "protected_extreme": nq_low,
                        "smt_reference": float(self._previous["es_low"]),
                    }
                )
            elif long["swept"] and not long["invalidated"]:
                long["protected_extreme"] = min(float(long["protected_extreme"]), nq_low)

    def _maybe_signal(
        self,
        bar: pd.Series,
        timestamp: pd.Timestamp,
        bar_close: pd.Timestamp,
        trades_today: int,
    ) -> Signal | None:
        if self._previous is None or trades_today >= self.max_trades_per_day or self._state["signaled"]:
            return None
        if bar_close.time() < self.start_time or bar_close.time() > self.end_time:
            return None
        if not self._prior_range_ok():
            return None

        reclaim_buffer = self.reclaim_buffer_ticks * self.tick_size
        close = float(bar["close"])
        midpoint = self._nq_midpoint()

        short = self._state["short"]
        if (
            short["swept"]
            and not short["invalidated"]
            and close <= float(self._previous["nq_high"]) - reclaim_buffer
            and close > midpoint
        ):
            self._state["signaled"] = True
            return self._signal("short", bar, timestamp, bar_close, short)

        long = self._state["long"]
        if (
            long["swept"]
            and not long["invalidated"]
            and close >= float(self._previous["nq_low"]) + reclaim_buffer
            and close < midpoint
        ):
            self._state["signaled"] = True
            return self._signal("long", bar, timestamp, bar_close, long)
        return None

    def _signal(
        self,
        direction: str,
        bar: pd.Series,
        timestamp: pd.Timestamp,
        signal_timestamp: pd.Timestamp,
        side: dict,
    ) -> Signal:
        midpoint = self._nq_midpoint()
        prev_high = float(self._previous["nq_high"])
        prev_low = float(self._previous["nq_low"])
        protected = float(side["protected_extreme"])
        report_fields = {
            "academic_source_key": "chartfanatics_smt_po3_midpoint_reversion",
            "setup_mode": self.setup_mode,
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "previous_nq_high": prev_high,
            "previous_nq_low": prev_low,
            "previous_nq_midpoint": midpoint,
            "previous_es_high": float(self._previous["es_high"]),
            "previous_es_low": float(self._previous["es_low"]),
            "smt_reference_level": float(side["smt_reference"]),
            "sweep_timestamp": side["sweep_timestamp"],
            "protected_extreme": protected,
            "sweep_buffer_ticks": self.sweep_buffer_ticks,
            "reclaim_buffer_ticks": self.reclaim_buffer_ticks,
            "signal_target_price": midpoint,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=f"nq_es_smt_po3_{direction}_midpoint_reversion",
            swept_level=prev_high if direction == "short" else prev_low,
            sweep_timestamp=side["sweep_timestamp"],
            sweep_high=protected if direction == "short" else float(bar["high"]),
            sweep_low=protected if direction == "long" else float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            breakout_level=prev_high if direction == "short" else prev_low,
            metadata={
                "setup_mode": self.setup_mode,
                "previous_nq_high": prev_high,
                "previous_nq_low": prev_low,
                "previous_nq_midpoint": midpoint,
                "previous_es_high": float(self._previous["es_high"]),
                "previous_es_low": float(self._previous["es_low"]),
                "smt_reference_level": float(side["smt_reference"]),
                "protected_extreme": protected,
                "signal_target_price": midpoint,
                "sweep_buffer_ticks": self.sweep_buffer_ticks,
                "reclaim_buffer_ticks": self.reclaim_buffer_ticks,
            },
            report_fields=report_fields,
        )

    def _finish_bar(self, bar: pd.Series) -> None:
        self._current["nq_high"] = _max_or_value(self._current["nq_high"], float(bar["high"]))
        self._current["nq_low"] = _min_or_value(self._current["nq_low"], float(bar["low"]))
        es_high = _finite_float(bar.get("es_high"))
        es_low = _finite_float(bar.get("es_low"))
        if es_high is not None:
            self._current["es_high"] = _max_or_value(self._current["es_high"], es_high)
        if es_low is not None:
            self._current["es_low"] = _min_or_value(self._current["es_low"], es_low)

    def _prior_range_ok(self) -> bool:
        if self._previous is None:
            return False
        width = float(self._previous["nq_high"]) - float(self._previous["nq_low"])
        return width >= self.min_prior_range_ticks * self.tick_size

    def _nq_midpoint(self) -> float:
        return (float(self._previous["nq_high"]) + float(self._previous["nq_low"])) / 2.0

    def _allows_short(self) -> bool:
        return self.setup_mode in {"prior_high_short", "prior_two_sided"}

    def _allows_long(self) -> bool:
        return self.setup_mode in {"prior_low_long", "prior_two_sided"}

    def _validate(self) -> None:
        allowed = {"prior_high_short", "prior_low_long", "prior_two_sided"}
        if self.setup_mode not in allowed:
            raise ValueError(f"setup_mode must be one of {sorted(allowed)}.")
        if self.tick_size <= 0 or self.bar_interval_minutes <= 0:
            raise ValueError("tick_size and bar_interval_minutes must be greater than 0.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        if min(self.sweep_buffer_ticks, self.reclaim_buffer_ticks, self.min_prior_range_ticks) < 0:
            raise ValueError("sweep/reclaim/range thresholds must be non-negative.")

    @staticmethod
    def _new_state() -> dict:
        return {
            "signaled": False,
            "short": {"swept": False, "invalidated": False},
            "long": {"swept": False, "invalidated": False},
        }


def _session_date(bar: pd.Series, timestamp: pd.Timestamp):
    value = bar.get("session_date")
    if value is None or pd.isna(value):
        return timestamp.date()
    return pd.Timestamp(value).date()


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _finite(value) -> bool:
    return _finite_float(value) is not None


def _max_or_value(current: float | None, value: float) -> float:
    return value if current is None else max(float(current), value)


def _min_or_value(current: float | None, value: float) -> float:
    return value if current is None else min(float(current), value)
