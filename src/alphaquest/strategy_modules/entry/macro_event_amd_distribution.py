from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class MacroEventAmdDistributionEntry:
    name = "macro_event_amd_distribution"

    _VALID_EVENT_SOURCES = {"bls", "fomc"}
    _VALID_SETUP_MODES = {
        "sellside_sweep_bullish_distribution",
        "buyside_sweep_bearish_distribution",
        "two_sided_distribution",
    }
    _VALID_DISPLACEMENT_REFERENCES = {"midpoint", "opposite_edge"}

    def __init__(self, params: dict):
        self.params = params
        self.event_source = str(params.get("event_source", "bls")).lower()
        self.event_calendar_csv = str(params.get("event_calendar_csv", ""))
        self.release_types = _release_types(params.get("release_types", ["employment_situation", "cpi"]))
        self.event_dates = _load_event_dates(self.event_source, self.event_calendar_csv, self.release_types)
        self.setup_mode = str(params.get("setup_mode", "two_sided_distribution")).lower()
        self.displacement_reference = str(params.get("displacement_reference", "opposite_edge")).lower()
        self.accumulation_start_time = parse_time(params.get("accumulation_start_time", "09:30:00"))
        self.accumulation_end_time = parse_time(params.get("accumulation_end_time", "09:45:00"))
        self.signal_start_time = parse_time(params.get("signal_start_time", params.get("accumulation_end_time", "09:45:00")))
        self.last_entry_time = parse_time(params.get("last_entry_time", "11:00:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_sweep_ticks = float(params.get("min_sweep_ticks", 8))
        self.min_displacement_ticks = float(params.get("min_displacement_ticks", 8))
        self.max_bars_after_sweep = max(0, int(params.get("max_bars_after_sweep", 8)))
        self.max_accumulation_range_ticks = float(params.get("max_accumulation_range_ticks", 1000000.0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.state_by_day: dict[date, dict] = {}

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._validate()
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _date(bar["session_date"])
        state = self._state(session_date)
        if state["completed"] or state["skip_day"]:
            return None
        if session_date not in self.event_dates:
            state["completed"] = True
            return None

        bar_close = self._bar_close_timestamp(timestamp)
        accumulation_start = _session_timestamp(timestamp, self.accumulation_start_time)
        accumulation_end = _session_timestamp(timestamp, self.accumulation_end_time)
        signal_start = _session_timestamp(timestamp, self.signal_start_time)
        last_entry = _session_timestamp(timestamp, self.last_entry_time)

        if bar_close <= accumulation_start:
            return None
        if timestamp < accumulation_end and bar_close <= accumulation_end:
            state["accumulation_bars"].append(bar.copy())
            if bar_close == accumulation_end:
                state["accumulation_range"] = self._build_accumulation_range(state)
            return None

        if state["accumulation_range"] is None:
            state["accumulation_range"] = self._build_accumulation_range(state)
            if state["skip_day"] or state["accumulation_range"] is None:
                return None

        if bar_close <= signal_start:
            return None
        if bar_close > last_entry:
            state["completed"] = True
            return None

        state["signal_bars_seen"] += 1
        signal = self._distribution_signal(bar, state, bar_close)
        if signal is not None:
            state["completed"] = True
        return signal

    def _distribution_signal(self, bar: pd.Series, state: dict, bar_close: pd.Timestamp) -> Signal | None:
        accumulation = state["accumulation_range"]
        close = _finite_float(bar.get("close"))
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        if close is None or high is None or low is None:
            state["skip_day"] = True
            return None

        if state["active_sweep"] is None:
            candidates = self._sweep_candidates(bar, accumulation)
            if len(candidates) != 1:
                return None
            state["active_sweep"] = self._new_sweep(candidates[0], bar, bar_close, state["signal_bars_seen"])

        sweep = state["active_sweep"]
        sweep["sweep_high"] = max(float(sweep["sweep_high"]), high)
        sweep["sweep_low"] = min(float(sweep["sweep_low"]), low)
        sweep["bars_after_sweep"] = state["signal_bars_seen"] - int(sweep["bar_index"])
        if state["signal_bars_seen"] - int(sweep["bar_index"]) > self.max_bars_after_sweep:
            state["active_sweep"] = None
            return None

        direction = "long" if sweep["side"] == "sellside" else "short"
        if not self._displaced(direction, close, accumulation):
            return None

        return self._signal(direction, bar, bar_close, accumulation, sweep, close)

    def _sweep_candidates(self, bar: pd.Series, accumulation: dict) -> list[str]:
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        if high is None or low is None:
            return []
        buffer = self.min_sweep_ticks * self.tick_size
        out: list[str] = []
        if self.setup_mode in {"sellside_sweep_bullish_distribution", "two_sided_distribution"}:
            if low <= float(accumulation["low"]) - buffer:
                out.append("sellside")
        if self.setup_mode in {"buyside_sweep_bearish_distribution", "two_sided_distribution"}:
            if high >= float(accumulation["high"]) + buffer:
                out.append("buyside")
        return out

    def _displaced(self, direction: str, close: float, accumulation: dict) -> bool:
        buffer = self.min_displacement_ticks * self.tick_size
        midpoint = (float(accumulation["high"]) + float(accumulation["low"])) / 2.0
        if direction == "long":
            reference = midpoint if self.displacement_reference == "midpoint" else float(accumulation["high"])
            return close >= reference + buffer
        reference = midpoint if self.displacement_reference == "midpoint" else float(accumulation["low"])
        return close <= reference - buffer

    def _signal(
        self,
        direction: str,
        bar: pd.Series,
        bar_close: pd.Timestamp,
        accumulation: dict,
        sweep: dict,
        close: float,
    ) -> Signal:
        swept_level = float(accumulation["low"] if direction == "long" else accumulation["high"])
        event_types = ",".join(sorted(self.event_dates[_date(bar["session_date"])]))
        report_fields = {
            "academic_source_key": "chartfanatics_amd_macro_event_liquidity_sweep_displacement",
            "setup_mode": self.setup_mode,
            "event_source": self.event_source,
            "event_calendar_csv": self.event_calendar_csv,
            "event_types": event_types,
            "event_session_date": _date(bar["session_date"]).isoformat(),
            "accumulation_start_timestamp": accumulation["start_timestamp"],
            "accumulation_end_timestamp": accumulation["end_timestamp"],
            "accumulation_high": accumulation["high"],
            "accumulation_low": accumulation["low"],
            "accumulation_open": accumulation["open"],
            "accumulation_width": accumulation["width"],
            "accumulation_width_ticks": accumulation["width_ticks"],
            "sweep_side": sweep["side"],
            "sweep_timestamp": sweep["timestamp"],
            "sweep_high": sweep["sweep_high"],
            "sweep_low": sweep["sweep_low"],
            "bars_after_sweep": int(sweep["bars_after_sweep"]),
            "displacement_reference": self.displacement_reference,
            "min_sweep_ticks": self.min_sweep_ticks,
            "min_displacement_ticks": self.min_displacement_ticks,
            "displacement_close": close,
            "signal_timestamp": bar_close,
            "intended_entry_timestamp": bar_close,
        }
        return Signal(
            direction=direction,
            level_type=f"macro_event_amd_{self.event_source}_{self.setup_mode}",
            swept_level=swept_level,
            sweep_timestamp=sweep["timestamp"],
            sweep_high=float(sweep["sweep_high"]),
            sweep_low=float(sweep["sweep_low"]),
            reclaim_timestamp=bar_close,
            opening_range_high=float(accumulation["high"]),
            opening_range_low=float(accumulation["low"]),
            opening_range_open=float(accumulation["open"]),
            opening_range_width=float(accumulation["width"]),
            breakout_level=swept_level,
            metadata={
                "setup_mode": self.setup_mode,
                "event_source": self.event_source,
                "event_types": event_types,
                "displacement_reference": self.displacement_reference,
                "min_sweep_ticks": self.min_sweep_ticks,
                "min_displacement_ticks": self.min_displacement_ticks,
                "intended_entry_timestamp": bar_close,
            },
            report_fields=report_fields,
        )

    def _new_sweep(self, side: str, bar: pd.Series, bar_close: pd.Timestamp, bar_index: int) -> dict:
        return {
            "side": side,
            "timestamp": bar_close,
            "bar_index": int(bar_index),
            "bars_after_sweep": 0,
            "sweep_high": float(bar["high"]),
            "sweep_low": float(bar["low"]),
        }

    def _build_accumulation_range(self, state: dict) -> dict | None:
        bars = state["accumulation_bars"]
        if not bars:
            state["skip_day"] = True
            return None
        try:
            acc_open = float(bars[0]["open"])
            acc_high = max(float(bar["high"]) for bar in bars)
            acc_low = min(float(bar["low"]) for bar in bars)
        except (KeyError, TypeError, ValueError):
            state["skip_day"] = True
            return None
        width = acc_high - acc_low
        width_ticks = width / self.tick_size if self.tick_size > 0 else float("nan")
        if not all(math.isfinite(value) for value in [acc_open, acc_high, acc_low, width, width_ticks]):
            state["skip_day"] = True
            return None
        if width <= 0 or width_ticks > self.max_accumulation_range_ticks:
            state["skip_day"] = True
            return None
        return {
            "open": acc_open,
            "high": acc_high,
            "low": acc_low,
            "width": width,
            "width_ticks": width_ticks,
            "start_timestamp": bars[0]["timestamp"],
            "end_timestamp": self._bar_close_timestamp(bars[-1]["timestamp"]),
        }

    def _state(self, session_date: date) -> dict:
        return self.state_by_day.setdefault(
            session_date,
            {
                "accumulation_bars": [],
                "accumulation_range": None,
                "active_sweep": None,
                "signal_bars_seen": 0,
                "completed": False,
                "skip_day": False,
            },
        )

    def _bar_close_timestamp(self, timestamp) -> pd.Timestamp:
        return pd.Timestamp(timestamp) + pd.Timedelta(minutes=self.bar_interval_minutes)

    def _validate(self) -> None:
        if self.event_source not in self._VALID_EVENT_SOURCES:
            raise ValueError(f"event_source must be one of {sorted(self._VALID_EVENT_SOURCES)}.")
        if self.setup_mode not in self._VALID_SETUP_MODES:
            raise ValueError(f"setup_mode must be one of {sorted(self._VALID_SETUP_MODES)}.")
        if self.displacement_reference not in self._VALID_DISPLACEMENT_REFERENCES:
            raise ValueError(
                f"displacement_reference must be one of {sorted(self._VALID_DISPLACEMENT_REFERENCES)}."
            )
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.min_sweep_ticks < 0 or self.min_displacement_ticks < 0:
            raise ValueError("min_sweep_ticks and min_displacement_ticks must be non-negative.")
        if self.accumulation_end_time <= self.accumulation_start_time:
            raise ValueError("accumulation_end_time must be after accumulation_start_time.")
        if self.last_entry_time <= self.signal_start_time:
            raise ValueError("last_entry_time must be after signal_start_time.")


def _load_event_dates(event_source: str, path: str, release_types: set[str]) -> dict[date, set[str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Macro event calendar not found: {path}")
    if event_source == "bls":
        return _load_bls_dates(csv_path, release_types)
    if event_source == "fomc":
        return _load_fomc_dates(csv_path)
    raise ValueError("event_source must be 'bls' or 'fomc'.")


def _load_bls_dates(path: Path, release_types: set[str]) -> dict[date, set[str]]:
    out: dict[date, set[str]] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if str(row.get("scheduled", "true")).lower() != "true":
                continue
            release_type = str(row["release_type"]).strip().lower()
            if release_type not in release_types:
                continue
            out.setdefault(date.fromisoformat(str(row["release_date"])), set()).add(release_type)
    return out


def _load_fomc_dates(path: Path) -> dict[date, set[str]]:
    out: dict[date, set[str]] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if str(row.get("scheduled", "true")).lower() != "true":
                continue
            out.setdefault(date.fromisoformat(str(row["event_date"])), set()).add("fomc_scheduled_decision")
    return out


def _release_types(value) -> set[str]:
    if isinstance(value, str):
        raw = [part.strip() for part in value.split(",")]
    else:
        raw = [str(part).strip() for part in value]
    out = {part.lower() for part in raw if part}
    return out or {"employment_situation", "cpi"}


def _session_timestamp(timestamp: pd.Timestamp, session_time) -> pd.Timestamp:
    return timestamp.replace(
        hour=session_time.hour,
        minute=session_time.minute,
        second=session_time.second,
        microsecond=0,
    )


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
