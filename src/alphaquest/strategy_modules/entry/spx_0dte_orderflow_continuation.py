from __future__ import annotations

from datetime import date
from pathlib import Path
import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.opening_gap_orderflow_fade import _orderflow_metrics
from alphaquest.strategy_modules.entry.spx_0dte_expiration_pressure import _bool
from alphaquest.utils.time import parse_time


class Spx0dteOrderflowContinuationEntry:
    name = "spx_0dte_orderflow_continuation"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "spx_0dte_orderflow_continuation")).lower()
        self.calendar_bucket = str(params.get("calendar_bucket", "all_available")).lower()
        self.direction_mode = str(params.get("direction_mode", "two_sided_continuation")).lower()
        self.flow_mode = str(params.get("flow_mode", "large20_imbalance")).lower()
        self.source_start = parse_time(params.get("source_start", "09:30:00"))
        self.signal_time = parse_time(params.get("signal_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_abs_move_ticks = float(params.get("min_abs_move_ticks", 8))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.04))
        self.exclude_standard_monthly = _bool(params.get("exclude_standard_monthly", True))
        self.event_calendar_csv = Path(str(params.get("event_calendar_csv", "")))
        self.calendar_by_date = self._load_calendar(self.event_calendar_csv)
        self.state_by_day: dict[date, dict] = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _date(bar["session_date"])
        state = self._state(session_date)
        if state["signaled"]:
            return None
        if state["session_open"] is None:
            state["session_open"] = _finite_float(bar.get("open"))

        row = self.calendar_by_date.get(session_date)
        if row is None or not self._calendar_row_matches(row):
            return None

        source_start = _session_timestamp(timestamp, self.source_start)
        signal_timestamp = _session_timestamp(timestamp, self.signal_time)
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)

        if timestamp >= source_start and bar_close <= signal_timestamp:
            state["source_window"] = self._aggregate_bar(
                state["source_window"],
                bar,
                source_start,
                signal_timestamp,
            )

        if bar_close != signal_timestamp:
            return None

        signal = self._signal(state, row, signal_timestamp)
        if signal is not None:
            state["signaled"] = True
        return signal

    def _state(self, session_date: date) -> dict:
        return self.state_by_day.setdefault(
            session_date,
            {
                "session_open": None,
                "source_window": None,
                "signaled": False,
            },
        )

    def _signal(self, state: dict, row: dict, signal_timestamp: pd.Timestamp) -> Signal | None:
        source = state.get("source_window")
        session_open = _finite_float(state.get("session_open"))
        if source is None or session_open is None or not self._window_complete(source):
            return None

        source_close = float(source["close"])
        open_to_signal_ticks = (source_close - session_open) / self.tick_size
        if not math.isfinite(open_to_signal_ticks):
            return None
        if abs(open_to_signal_ticks) < self.min_abs_move_ticks:
            return None

        metrics = _orderflow_metrics(source)
        primary, secondary = self._flow_values(metrics)
        if primary is None:
            return None

        direction = self._direction(open_to_signal_ticks, primary, secondary)
        if direction is None:
            return None

        report_fields = {
            "academic_source_key": "spx_0dte_orderflow_continuation",
            "setup_mode": self.setup_mode,
            "spx_0dte_signal_timestamp": signal_timestamp,
            "spx_0dte_session_date": row["signal_date"],
            "spx_0dte_weekday": row["weekday"],
            "spx_0dte_weekday_name": row["weekday_name"],
            "spx_0dte_calendar_bucket": self.calendar_bucket,
            "spx_0dte_exclude_standard_monthly": self.exclude_standard_monthly,
            "spx_0dte_is_standard_monthly": row["is_standard_monthly"],
            "spx_0dte_is_quarterly_month": row["is_quarterly_month"],
            "direction_mode": self.direction_mode,
            "flow_mode": self.flow_mode,
            "session_open": session_open,
            "source_window_start_timestamp": source["start_timestamp"],
            "source_window_end_timestamp": source["end_timestamp"],
            "source_window_open": float(source["open"]),
            "source_window_high": float(source["high"]),
            "source_window_low": float(source["low"]),
            "source_window_close": source_close,
            "source_window_return_ticks": open_to_signal_ticks,
            "source_window_volume": float(source["volume"]),
            "source_window_signed_volume": float(source["signed_volume"]),
            "source_window_large10_signed_volume": float(source["large10_signed_volume"]),
            "source_window_large20_signed_volume": float(source["large20_signed_volume"]),
            "source_window_imbalance": metrics["signed_imbalance"],
            "source_window_large10_imbalance": metrics["large10_imbalance"],
            "source_window_large20_imbalance": metrics["large20_imbalance"],
            "primary_orderflow_imbalance": primary,
            "secondary_orderflow_imbalance": secondary,
            "min_abs_move_ticks": self.min_abs_move_ticks,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=f"spx_0dte_orderflow_{self.setup_mode}",
            swept_level=session_open,
            sweep_timestamp=signal_timestamp,
            sweep_high=float(source["high"]),
            sweep_low=float(source["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "calendar_bucket": self.calendar_bucket,
                "direction_mode": self.direction_mode,
                "flow_mode": self.flow_mode,
                "open_to_signal_ticks": open_to_signal_ticks,
                "primary_orderflow_imbalance": primary,
                "secondary_orderflow_imbalance": secondary,
                "direction": direction,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _aggregate_bar(
        self,
        aggregate: dict | None,
        bar: pd.Series,
        start: pd.Timestamp,
        end: pd.Timestamp,
    ) -> dict:
        if aggregate is None or aggregate.get("start_timestamp") != start or aggregate.get("end_timestamp") != end:
            return {
                "start_timestamp": start,
                "end_timestamp": end,
                "open": float(bar["open"]),
                "high": float(bar["high"]),
                "low": float(bar["low"]),
                "close": float(bar["close"]),
                "volume": _finite_float(bar.get("volume")) or 0.0,
                "signed_volume": _finite_float(bar.get("signed_volume")) or 0.0,
                "large10_volume": _finite_float(bar.get("large10_volume")) or 0.0,
                "large10_signed_volume": _finite_float(bar.get("large10_signed_volume")) or 0.0,
                "large20_volume": _finite_float(bar.get("large20_volume")) or 0.0,
                "large20_signed_volume": _finite_float(bar.get("large20_signed_volume")) or 0.0,
                "bar_count": 1,
            }

        aggregate["high"] = max(float(aggregate["high"]), float(bar["high"]))
        aggregate["low"] = min(float(aggregate["low"]), float(bar["low"]))
        aggregate["close"] = float(bar["close"])
        for column in [
            "volume",
            "signed_volume",
            "large10_volume",
            "large10_signed_volume",
            "large20_volume",
            "large20_signed_volume",
        ]:
            aggregate[column] = float(aggregate[column]) + (_finite_float(bar.get(column)) or 0.0)
        aggregate["bar_count"] += 1
        return aggregate

    def _window_complete(self, window: dict) -> bool:
        start = pd.Timestamp(window["start_timestamp"])
        end = pd.Timestamp(window["end_timestamp"])
        minutes = (end - start).total_seconds() / 60
        expected = max(1, int(math.ceil(minutes / self.bar_interval_minutes)))
        return int(window.get("bar_count", 0)) >= expected

    def _flow_values(self, metrics: dict) -> tuple[float | None, float | None]:
        if self.flow_mode in {"signed_imbalance", "all_volume_imbalance"}:
            return metrics["signed_imbalance"], None
        if self.flow_mode in {"large10_imbalance", "large10"}:
            return metrics["large10_imbalance"], None
        if self.flow_mode in {"large20_imbalance", "large20"}:
            return metrics["large20_imbalance"], None
        if self.flow_mode in {"broad_large_alignment", "signed_and_large20"}:
            return metrics["large20_imbalance"], metrics["signed_imbalance"]
        raise ValueError(
            "spx_0dte_orderflow_continuation flow_mode must be one of: "
            "signed_imbalance, large10_imbalance, large20_imbalance, broad_large_alignment."
        )

    def _direction(self, open_to_signal_ticks: float, primary: float, secondary: float | None) -> str | None:
        threshold = self.min_orderflow_imbalance
        long_ok = open_to_signal_ticks >= self.min_abs_move_ticks and primary >= threshold and (
            secondary is None or secondary >= 0.0
        )
        short_ok = open_to_signal_ticks <= -self.min_abs_move_ticks and primary <= -threshold and (
            secondary is None or secondary <= 0.0
        )
        if self.direction_mode in {"two_sided_continuation", "two_sided"}:
            if long_ok:
                return "long"
            if short_ok:
                return "short"
            return None
        if self.direction_mode in {"long_only_continuation", "long_only"}:
            return "long" if long_ok else None
        if self.direction_mode in {"short_only_continuation", "short_only"}:
            return "short" if short_ok else None
        raise ValueError(
            "spx_0dte_orderflow_continuation direction_mode must be one of: "
            "two_sided_continuation, long_only_continuation, short_only_continuation."
        )

    def _calendar_row_matches(self, row: dict) -> bool:
        if self.exclude_standard_monthly and bool(row["is_standard_monthly"]):
            return False
        if self.calendar_bucket == "full_week":
            return bool(row["is_full_week_0dte"])
        if self.calendar_bucket == "new_tue_thu":
            return bool(row["is_new_tue_thu_0dte"])
        if self.calendar_bucket == "mon_wed_fri":
            return bool(row["is_mwf_0dte"])
        if self.calendar_bucket == "all_available":
            return bool(row["is_spx_0dte"])
        raise ValueError("calendar_bucket must be full_week, new_tue_thu, mon_wed_fri, or all_available.")

    def _load_calendar(self, path: Path) -> dict[date, dict]:
        if not path:
            raise ValueError("event_calendar_csv is required.")
        if not path.exists():
            raise FileNotFoundError(f"SPX 0DTE calendar does not exist: {path}")

        df = pd.read_csv(path)
        required = {
            "signal_date",
            "weekday",
            "weekday_name",
            "is_spx_0dte",
            "is_full_week_0dte",
            "is_new_tue_thu_0dte",
            "is_mwf_0dte",
            "is_standard_monthly",
            "is_quarterly_month",
        }
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"SPX 0DTE calendar missing column(s): {sorted(missing)}")

        calendar: dict[date, dict] = {}
        for raw in df.to_dict("records"):
            signal_date = pd.Timestamp(raw["signal_date"]).date()
            if signal_date in calendar:
                raise ValueError(f"Duplicate SPX 0DTE signal date: {signal_date}")
            calendar[signal_date] = {
                "signal_date": signal_date.isoformat(),
                "weekday": int(raw["weekday"]),
                "weekday_name": str(raw["weekday_name"]),
                "is_spx_0dte": _bool(raw["is_spx_0dte"]),
                "is_full_week_0dte": _bool(raw["is_full_week_0dte"]),
                "is_new_tue_thu_0dte": _bool(raw["is_new_tue_thu_0dte"]),
                "is_mwf_0dte": _bool(raw["is_mwf_0dte"]),
                "is_standard_monthly": _bool(raw["is_standard_monthly"]),
                "is_quarterly_month": _bool(raw["is_quarterly_month"]),
            }
        return calendar

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.min_abs_move_ticks < 0:
            raise ValueError("min_abs_move_ticks must be non-negative.")
        if not 0 <= self.min_orderflow_imbalance <= 1:
            raise ValueError("min_orderflow_imbalance must be in [0, 1].")


def _session_timestamp(timestamp: pd.Timestamp, value) -> pd.Timestamp:
    return timestamp.replace(
        hour=value.hour,
        minute=value.minute,
        second=value.second,
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
