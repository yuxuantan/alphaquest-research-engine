from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class TreasuryRateOrderflowStateEntry:
    name = "treasury_rate_orderflow_state"

    _FLOW_COLUMNS = {
        "signed_volume": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }
    _RANK_COLUMNS = {
        "dgs10_1d": "dgs10_change_1d_rank_252",
        "dgs2_1d": "dgs2_change_1d_rank_252",
        "curve_1d": "curve_change_1d_rank_252",
        "dgs10_5d": "dgs10_change_5d_rank_252",
        "curve_5d": "curve_change_5d_rank_252",
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "rate_two_sided_confirmation")).lower()
        self.rank_mode = str(params.get("rank_mode", "dgs10_1d")).lower()
        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/es_treasury_rate_state_features_20110103_20260609.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.signal_times = tuple(parse_time(value) for value in params.get("signal_times", ["10:00:00"]))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.rate_rank_threshold = float(params.get("rate_rank_threshold", 0.70))
        self.min_es_move_ticks = float(params.get("min_es_move_ticks", 2.0))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.0))
        self.min_flow_volume = float(params.get("min_flow_volume", 0.0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self._validate()
        self.state_by_day: dict[date, dict] = {}

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None
        session_date = _date(bar.get("session_date", bar.get("timestamp")))
        state = self.state_by_day.setdefault(session_date, self._new_state())
        self._update_state(bar, state)
        if state["signaled"]:
            return None

        signal_timestamp = pd.Timestamp(bar["timestamp"]) + pd.Timedelta(minutes=self.bar_interval_minutes)
        if signal_timestamp.time() not in self.signal_times:
            return None
        row = self.features.get(session_date)
        if row is None:
            return None
        direction, driver_column, driver_value = self._direction_from_features(row, state)
        if direction is None:
            return None
        flow = self._confirmation_flow(state, direction)
        if flow is None:
            return None
        signed_volume, flow_volume, imbalance = flow

        state["signaled"] = True
        report_fields = {
            "academic_source_key": "treasury_rate_orderflow_confirmation",
            "setup_mode": self.setup_mode,
            "rank_mode": self.rank_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "treasury_observation_date": row.get("observation_date"),
            "availability_rule": "latest Treasury observation strictly before ES session_date",
            "rate_driver_column": driver_column,
            "rate_driver_value": driver_value,
            "rate_rank_threshold": self.rate_rank_threshold,
            "dgs10": row.get("dgs10"),
            "dgs2": row.get("dgs2"),
            "curve_10y2y": row.get("curve_10y2y"),
            "dgs10_change_1d": row.get("dgs10_change_1d"),
            "dgs2_change_1d": row.get("dgs2_change_1d"),
            "curve_change_1d": row.get("curve_change_1d"),
            "dgs10_change_5d": row.get("dgs10_change_5d"),
            "curve_change_5d": row.get("curve_change_5d"),
            "flow_mode": self.flow_mode,
            "session_open": state["session_open"],
            "confirmation_close": bar.get("close"),
            "es_move_ticks": state["move_ticks"],
            "min_es_move_ticks": self.min_es_move_ticks,
            "confirmation_signed_volume": signed_volume,
            "confirmation_flow_volume": flow_volume,
            "confirmation_orderflow_imbalance": imbalance,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
        }
        return Signal(
            direction=direction,
            level_type=f"treasury_rate_orderflow_{self.rank_mode}_{self.setup_mode}_{direction}",
            swept_level=float(state["session_open"]),
            sweep_timestamp=pd.Timestamp(bar["timestamp"]),
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "rank_mode": self.rank_mode,
                "rate_driver_column": driver_column,
                "rate_driver_value": driver_value,
                "flow_mode": self.flow_mode,
                "orderflow_imbalance": imbalance,
                "es_move_ticks": state["move_ticks"],
            },
            report_fields=report_fields,
        )

    def _new_state(self) -> dict:
        return {
            "signaled": False,
            "session_open": None,
            "last_close": None,
            "signed_volume": 0.0,
            "volume": 0.0,
            "large10_signed_volume": 0.0,
            "large10_volume": 0.0,
            "large20_signed_volume": 0.0,
            "large20_volume": 0.0,
            "move_ticks": float("nan"),
        }

    def _update_state(self, bar: pd.Series, state: dict) -> None:
        if state["session_open"] is None:
            open_ = _finite_float(bar.get("open"))
            if open_ is not None:
                state["session_open"] = open_
        close = _finite_float(bar.get("close"))
        if close is not None:
            state["last_close"] = close
            if state["session_open"] is not None:
                state["move_ticks"] = (close - float(state["session_open"])) / self.tick_size
        for column in (
            "signed_volume",
            "volume",
            "large10_signed_volume",
            "large10_volume",
            "large20_signed_volume",
            "large20_volume",
        ):
            value = _finite_float(bar.get(column))
            if value is not None:
                state[column] += value

    def _direction_from_features(self, row: dict, state: dict) -> tuple[str | None, str, float]:
        move_ticks = _finite_float(state.get("move_ticks"))
        if move_ticks is None:
            return None, "", float("nan")
        rank_column = self._RANK_COLUMNS[self.rank_mode]
        rank = _finite_float(row.get(rank_column))
        if rank is None:
            return None, rank_column, float("nan")
        low_tail = 1.0 - self.rate_rank_threshold
        if self.setup_mode != "rate_two_sided_confirmation":
            raise ValueError(f"Unsupported setup_mode: {self.setup_mode}")
        if rank >= self.rate_rank_threshold and move_ticks <= -self.min_es_move_ticks:
            return "short", rank_column, rank
        if rank <= low_tail and move_ticks >= self.min_es_move_ticks:
            return "long", rank_column, rank
        return None, rank_column, rank

    def _confirmation_flow(self, state: dict, direction: str) -> tuple[float, float, float] | None:
        signed_col, total_col = self._FLOW_COLUMNS[self.flow_mode]
        signed_volume = _finite_float(state.get(signed_col))
        total_volume = _finite_float(state.get(total_col))
        if signed_volume is None or total_volume is None or total_volume <= 0:
            return None
        if total_volume < self.min_flow_volume:
            return None
        imbalance = signed_volume / total_volume
        if direction == "long" and imbalance < self.min_orderflow_imbalance:
            return None
        if direction == "short" and imbalance > -self.min_orderflow_imbalance:
            return None
        return signed_volume, total_volume, imbalance

    def _validate(self) -> None:
        if self.setup_mode != "rate_two_sided_confirmation":
            raise ValueError("entry.params.setup_mode is unsupported.")
        if self.rank_mode not in self._RANK_COLUMNS:
            raise ValueError(f"entry.params.rank_mode must be one of {sorted(self._RANK_COLUMNS)}.")
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError(f"entry.params.flow_mode must be one of {sorted(self._FLOW_COLUMNS)}.")
        if not self.signal_times:
            raise ValueError("entry.params.signal_times must define at least one signal time.")
        if self.bar_interval_minutes <= 0 or self.tick_size <= 0:
            raise ValueError("entry.params.bar_interval_minutes and tick_size must be greater than zero.")
        if not 0.5 <= self.rate_rank_threshold < 1.0:
            raise ValueError("entry.params.rate_rank_threshold must be in [0.5, 1.0).")
        if self.min_es_move_ticks < 0 or self.min_orderflow_imbalance < 0 or self.min_flow_volume < 0:
            raise ValueError("entry.params confirmation thresholds must be non-negative.")
        if self.max_trades_per_day < 1:
            raise ValueError("entry.params.max_trades_per_day must be positive.")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Treasury rate feature CSV not found: {path}")
    out: dict[date, dict[str, float | str]] = {}
    string_columns = {"observation_date"}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            session_date = date.fromisoformat(str(row["session_date"]))
            out[session_date] = {
                key: (value if key in string_columns else _nan_float(value))
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
