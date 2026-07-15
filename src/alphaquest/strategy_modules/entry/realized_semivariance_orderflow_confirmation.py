from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class RealizedSemivarianceOrderflowConfirmationEntry:
    name = "realized_semivariance_orderflow_confirmation"

    _FLOW_PREFIX = {
        "signed": "trade_orderflow_imbalance",
        "signed_volume": "trade_orderflow_imbalance",
        "large10": "trade_orderflow_large10_imbalance",
        "large20": "trade_orderflow_large20_imbalance",
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "badvol_confirmed_continuation")).lower()
        self.direction_mode = str(params.get("direction_mode", "high_short")).lower()
        self.feature_csv = str(
            params.get("feature_csv", "data/external/es_realized_semivariance_features_20110103_20260609.csv")
        )
        self.features = _load_features(self.feature_csv)
        self.value_column = str(params.get("value_column", "prior_downside_semivariance_1d"))
        self.rank_column = str(params.get("rank_column", "downside1_rank_252"))
        self.semivar_rank_threshold = float(params.get("semivar_rank_threshold", 0.35))
        entry_times = params.get("entry_times")
        if entry_times is None:
            entry_times = [params.get("entry_time", "10:30:00")]
        if isinstance(entry_times, str):
            entry_times = [entry_times]
        self.entry_times = tuple(parse_time(value) for value in entry_times)
        self.entry_time = self.entry_times[0]
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.flow_mode = str(params.get("flow_mode", "signed")).lower()
        self.flow_window_bars = int(params.get("flow_window_bars", 12))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.0))
        self.min_session_move_ticks = float(params.get("min_session_move_ticks", 0.0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.state_by_day: dict[date, dict] = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _date(bar["session_date"])
        state = self.state_by_day.setdefault(session_date, {"signaled": False, "session_open": None})
        if state["session_open"] is None:
            state["session_open"] = _finite_float(bar.get("open"))
        if state["signaled"]:
            return None

        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if bar_close.time() not in self.entry_times:
            return None
        signal_timestamp = bar_close

        row = self.features.get(session_date)
        if row is None:
            return None
        rank = _finite_float(row.get(self.rank_column))
        value = _finite_float(row.get(self.value_column))
        if rank is None or value is None:
            return None

        direction = self._direction(rank)
        if direction is None:
            return None

        session_open = _finite_float(state["session_open"])
        current_close = _finite_float(bar.get("close"))
        if session_open is None or current_close is None:
            return None
        session_move_ticks = (current_close - session_open) / self.tick_size
        if direction == "long" and session_move_ticks < self.min_session_move_ticks:
            return None
        if direction == "short" and session_move_ticks > -self.min_session_move_ticks:
            return None

        flow_imbalance = self._flow_imbalance(bar)
        if flow_imbalance is None:
            return None
        if direction == "long" and flow_imbalance < self.min_orderflow_imbalance:
            return None
        if direction == "short" and flow_imbalance > -self.min_orderflow_imbalance:
            return None

        report_fields = {
            "academic_source_key": "realized_semivariance_plus_orderflow_confirmation",
            "setup_mode": self.setup_mode,
            "direction_mode": self.direction_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "semivar_value_column": self.value_column,
            "semivar_value": value,
            "semivar_rank_column": self.rank_column,
            "semivar_rank": rank,
            "semivar_rank_threshold": self.semivar_rank_threshold,
            "prior_close": row.get("prior_close"),
            "prior_rth_return": row.get("prior_rth_return"),
            "prior_realized_variance": row.get("prior_realized_variance"),
            "prior_downside_semivariance_1d": row.get("prior_downside_semivariance_1d"),
            "prior_upside_semivariance_1d": row.get("prior_upside_semivariance_1d"),
            "prior_downside_share_1d": row.get("prior_downside_share_1d"),
            "prior_semivariance_balance_1d": row.get("prior_semivariance_balance_1d"),
            "session_open": session_open,
            "signal_close": current_close,
            "session_move_ticks": session_move_ticks,
            "min_session_move_ticks": self.min_session_move_ticks,
            "flow_mode": self.flow_mode,
            "flow_window_bars": self.flow_window_bars,
            "orderflow_imbalance": flow_imbalance,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"realized_semivariance_orderflow_confirmation_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "direction_mode": self.direction_mode,
                "semivar_rank_column": self.rank_column,
                "semivar_rank": rank,
                "semivar_value_column": self.value_column,
                "semivar_value": value,
                "session_move_ticks": session_move_ticks,
                "orderflow_imbalance": flow_imbalance,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _direction(self, rank: float) -> str | None:
        high_cutoff = 1.0 - self.semivar_rank_threshold
        if self.direction_mode == "high_long":
            return "long" if rank >= high_cutoff else None
        if self.direction_mode == "high_short":
            return "short" if rank >= high_cutoff else None
        if self.direction_mode == "low_long":
            return "long" if rank <= self.semivar_rank_threshold else None
        if self.direction_mode == "low_short":
            return "short" if rank <= self.semivar_rank_threshold else None
        if self.direction_mode == "two_sided_bad_good":
            if rank >= high_cutoff:
                return "short"
            if rank <= self.semivar_rank_threshold:
                return "long"
            return None
        raise ValueError(
            f"Unsupported direction_mode for realized_semivariance_orderflow_confirmation: {self.direction_mode}"
        )

    def _flow_imbalance(self, bar: pd.Series) -> float | None:
        prefix = self._FLOW_PREFIX[self.flow_mode]
        column = f"{prefix}_{self.flow_window_bars}"
        return _finite_float(bar.get(column))

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if not self.entry_times:
            raise ValueError("entry_times must contain at least one decision time.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if not 0 < self.semivar_rank_threshold <= 0.5:
            raise ValueError("semivar_rank_threshold must be in (0, 0.5].")
        if self.flow_mode not in self._FLOW_PREFIX:
            raise ValueError(f"flow_mode must be one of: {sorted(self._FLOW_PREFIX)}.")
        if self.flow_window_bars <= 0:
            raise ValueError("flow_window_bars must be greater than zero.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("min_orderflow_imbalance must be non-negative.")
        if self.min_session_move_ticks < 0:
            raise ValueError("min_session_move_ticks must be non-negative.")


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
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
