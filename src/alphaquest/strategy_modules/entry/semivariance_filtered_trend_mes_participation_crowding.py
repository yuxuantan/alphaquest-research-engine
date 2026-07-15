from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class SemivarianceFilteredTrendMesParticipationCrowdingEntry:
    name = "semivariance_filtered_trend_mes_participation_crowding"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", self.name))
        self.signal_mode = str(params.get("signal_mode", "first_signal_in_window")).lower()
        self.entry_time = parse_time(params.get("entry_time", "10:30:00"))
        self.start_time = parse_time(params.get("start_time", params.get("entry_start_time", self.entry_time)))
        self.end_time = parse_time(params.get("end_time", params.get("last_entry_time", self.entry_time)))
        self.flatten_time = parse_time(params.get("flatten_time", "12:00:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.lookback_minutes = int(params.get("lookback_minutes", 15))
        self.trend_lookback_minutes = int(params.get("trend_lookback_minutes", 30))
        self.rank_window = int(params.get("rank_window", 252))
        self.share_mode = str(params.get("share_mode", "notional")).lower()
        self.return_column_prefix = str(params.get("return_column_prefix", "es")).lower()
        self.direction = str(params.get("direction", "both")).lower()
        self.share_rank_min = float(params.get("share_rank_min", 0.55))
        self.min_abs_return_ticks = float(params.get("min_abs_return_ticks", 4.0))
        self.min_trend_return_ticks = float(params.get("min_trend_return_ticks", 4.0))
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/es_realized_semivariance_features_20110103_20260609.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.semivar_value_column = str(params.get("semivar_value_column", "prior_downside_semivariance_1d"))
        self.semivar_rank_column = str(params.get("semivar_rank_column", "downside1_rank_252"))
        self.semivar_rank_min = float(params.get("semivar_rank_min", 0.55))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.stop_pct = float(params.get("stop_pct", 0.003))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        state = self._state(bar, timestamp)
        self._append_history(state, bar_close, bar)

        if trades_today >= self.max_trades_per_day or state["signaled"]:
            return None

        signal_timestamp = self._signal_timestamp(timestamp, bar_close)
        if signal_timestamp is None:
            return None

        session_date = _date(bar.get("session_date", timestamp.date()))
        semivar = self._semivariance(session_date)
        if semivar is None or semivar["rank"] < self.semivar_rank_min:
            return None

        metrics = self._metrics(bar)
        if metrics is None:
            return None
        if metrics["share_rank"] < self.share_rank_min:
            return None
        if abs(metrics["es_return_ticks"]) < self.min_abs_return_ticks:
            return None

        trend = self._trend_return_ticks(state, signal_timestamp)
        if trend is None:
            return None

        direction = self._direction(metrics["es_return_ticks"], trend["trend_return_ticks"])
        if direction is None:
            return None

        state["signaled"] = True
        current_close = float(bar["close"])
        report_fields = {
            "academic_source_key": "mes_crowding_trend_pullback_high_semivariance_regime",
            "setup_mode": self.setup_mode,
            "feature_method": "completed_bar_mes_participation_crowding_with_prior_trend_and_semivariance_filter",
            "signal_mode": self.signal_mode,
            "signal_window_start": self.start_time.strftime("%H:%M:%S"),
            "signal_window_end": self.end_time.strftime("%H:%M:%S"),
            "share_mode": self.share_mode,
            "lookback_minutes": self.lookback_minutes,
            "trend_lookback_minutes": self.trend_lookback_minutes,
            "rank_window": self.rank_window,
            "configured_direction": self.direction,
            "return_column_prefix": self.return_column_prefix,
            "share_rank": metrics["share_rank"],
            "share_value": metrics["share_value"],
            "es_pullback_return_ticks": metrics["es_return_ticks"],
            "pullback_return_ticks": metrics["es_return_ticks"],
            "pullback_return_column": metrics["return_col"],
            "trend_return_ticks": trend["trend_return_ticks"],
            "trend_start_timestamp": trend["trend_start_timestamp"],
            "trend_end_timestamp": trend["trend_end_timestamp"],
            "share_rank_min": self.share_rank_min,
            "min_abs_return_ticks": self.min_abs_return_ticks,
            "min_trend_return_ticks": self.min_trend_return_ticks,
            "semivariance_filter": "prior_session_high_semivariance_regime",
            "feature_csv": self.feature_csv,
            "semivar_feature_session_date": session_date.isoformat(),
            "semivar_value_column": self.semivar_value_column,
            "semivar_value": semivar["value"],
            "semivar_rank_column": self.semivar_rank_column,
            "semivar_rank": semivar["rank"],
            "semivar_rank_min": self.semivar_rank_min,
            "crowding_signal_timestamp": signal_timestamp,
            "crowding_intended_entry_timestamp": signal_timestamp,
            "signal_close_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "swept_level": current_close,
            "sweep_timestamp": timestamp,
            "sweep_high": float(bar["high"]),
            "sweep_low": float(bar["low"]),
            "reclaim_timestamp": signal_timestamp,
        }
        return Signal(
            direction=direction,
            level_type=f"semivariance_filtered_trend_mes_participation_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "signal_mode": self.signal_mode,
                "share_mode": self.share_mode,
                "lookback_minutes": self.lookback_minutes,
                "trend_lookback_minutes": self.trend_lookback_minutes,
                "share_rank_min": self.share_rank_min,
                "return_column_prefix": self.return_column_prefix,
                "min_abs_return_ticks": self.min_abs_return_ticks,
                "min_trend_return_ticks": self.min_trend_return_ticks,
                "semivar_rank_column": self.semivar_rank_column,
                "semivar_rank": semivar["rank"],
                "semivar_value_column": self.semivar_value_column,
                "semivar_value": semivar["value"],
                "semivar_rank_min": self.semivar_rank_min,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _signal_timestamp(self, timestamp: pd.Timestamp, bar_close: pd.Timestamp) -> pd.Timestamp | None:
        if self.signal_mode == "fixed_time":
            signal_timestamp = timestamp.replace(
                hour=self.entry_time.hour,
                minute=self.entry_time.minute,
                second=self.entry_time.second,
                microsecond=0,
            )
            return signal_timestamp if bar_close == signal_timestamp else None
        if self.signal_mode in {"first_signal_in_window", "first_in_window"}:
            if bar_close.time() < self.start_time or bar_close.time() > self.end_time:
                return None
            return bar_close
        raise ValueError("signal_mode must be fixed_time or first_signal_in_window.")

    def _state(self, bar: pd.Series, timestamp: pd.Timestamp) -> dict:
        session_date = bar.get("session_date", timestamp.date())
        state = self.state_by_day.get(session_date)
        if state is None:
            state = {"signaled": False, "history": {}}
            self.state_by_day[session_date] = state
        return state

    def _append_history(self, state: dict, bar_close: pd.Timestamp, bar: pd.Series) -> None:
        close = _finite_float(bar.get("close"))
        if close is None:
            return
        state["history"][bar_close] = close
        max_minutes = self.lookback_minutes + self.trend_lookback_minutes + 5
        cutoff = bar_close - pd.Timedelta(minutes=max_minutes)
        state["history"] = {
            timestamp: value
            for timestamp, value in state["history"].items()
            if timestamp >= cutoff
        }

    def _metrics(self, bar: pd.Series) -> dict[str, float] | None:
        suffix = str(self.lookback_minutes)
        if self.share_mode == "trade":
            share_col = f"mes_trade_share_{suffix}"
            rank_col = f"mes_trade_share_{suffix}_rank{self.rank_window}"
        else:
            share_col = f"mes_participation_share_{suffix}"
            rank_col = f"mes_participation_share_{suffix}_rank{self.rank_window}"
        return_col = f"{self.return_column_prefix}_return_ticks_{suffix}"
        share_rank = _finite_float(bar.get(rank_col))
        share_value = _finite_float(bar.get(share_col))
        es_return_ticks = _finite_float(bar.get(return_col))
        if None in {share_rank, share_value, es_return_ticks}:
            return None
        return {
            "share_rank": share_rank,
            "share_value": share_value,
            "es_return_ticks": es_return_ticks,
            "return_col": return_col,
        }

    def _semivariance(self, session_date: date) -> dict[str, float] | None:
        row = self.features.get(session_date)
        if row is None:
            return None
        rank = _finite_float(row.get(self.semivar_rank_column))
        value = _finite_float(row.get(self.semivar_value_column))
        if rank is None or value is None:
            return None
        return {"rank": rank, "value": value}

    def _trend_return_ticks(self, state: dict, signal_timestamp: pd.Timestamp) -> dict[str, object] | None:
        trend_end_timestamp = signal_timestamp - pd.Timedelta(minutes=self.lookback_minutes)
        trend_start_timestamp = trend_end_timestamp - pd.Timedelta(minutes=self.trend_lookback_minutes)
        close_end = _finite_float(state["history"].get(trend_end_timestamp))
        close_start = _finite_float(state["history"].get(trend_start_timestamp))
        if close_end is None or close_start is None:
            return None
        trend_return_ticks = (close_end - close_start) / self.tick_size
        if not math.isfinite(trend_return_ticks):
            return None
        return {
            "trend_start_timestamp": trend_start_timestamp,
            "trend_end_timestamp": trend_end_timestamp,
            "trend_return_ticks": trend_return_ticks,
        }

    def _direction(self, es_return_ticks: float, trend_return_ticks: float) -> str | None:
        if (
            es_return_ticks <= -self.min_abs_return_ticks
            and trend_return_ticks >= self.min_trend_return_ticks
            and self.direction in {"long", "both"}
        ):
            return "long"
        if (
            es_return_ticks >= self.min_abs_return_ticks
            and trend_return_ticks <= -self.min_trend_return_ticks
            and self.direction in {"short", "both"}
        ):
            return "short"
        return None

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.lookback_minutes <= 0:
            raise ValueError("lookback_minutes must be greater than 0.")
        if self.trend_lookback_minutes <= 0:
            raise ValueError("trend_lookback_minutes must be greater than 0.")
        if self.rank_window <= 0:
            raise ValueError("rank_window must be greater than 0.")
        if self.share_mode not in {"notional", "trade"}:
            raise ValueError("share_mode must be notional or trade.")
        if not self.return_column_prefix.replace("_", "").isalnum():
            raise ValueError("return_column_prefix must contain only letters, numbers, or underscores.")
        if self.direction not in {"long", "short", "both"}:
            raise ValueError("direction must be long, short, or both.")
        if self.signal_mode not in {"fixed_time", "first_signal_in_window", "first_in_window"}:
            raise ValueError("signal_mode must be fixed_time or first_signal_in_window.")
        if self.start_time > self.end_time:
            raise ValueError("start_time must be at or before end_time.")
        if not 0 <= self.share_rank_min <= 1:
            raise ValueError("share_rank_min must be between 0 and 1.")
        if not 0 <= self.semivar_rank_min <= 1:
            raise ValueError("semivar_rank_min must be between 0 and 1.")
        if self.min_abs_return_ticks < 0:
            raise ValueError("min_abs_return_ticks must be non-negative.")
        if self.min_trend_return_ticks < 0:
            raise ValueError("min_trend_return_ticks must be non-negative.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if not self.semivar_rank_column:
            raise ValueError("semivar_rank_column must be non-empty.")
        if not self.semivar_value_column:
            raise ValueError("semivar_value_column must be non-empty.")


def _load_features(path: str) -> dict[date, dict[str, float]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Lagged realized-semivariance feature CSV not found: {path}")
    out: dict[date, dict[str, float]] = {}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            session_date = date.fromisoformat(str(row["session_date"]))
            out[session_date] = {
                key: _nan_float(value)
                for key, value in row.items()
                if key != "session_date"
            }
    return out


def _date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


def _nan_float(value) -> float:
    if value in {None, ""}:
        return float("nan")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
