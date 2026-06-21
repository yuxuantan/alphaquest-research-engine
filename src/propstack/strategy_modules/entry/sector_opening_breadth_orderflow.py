from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class SectorOpeningBreadthOrderflowEntry:
    name = "sector_opening_breadth_orderflow"

    _FLOW_COLUMNS = {
        "signed_volume": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }

    def __init__(self, params: dict):
        self.params = params
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/es_sector_opening_breadth_features_20110103_20260609.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.setup_mode = str(params.get("setup_mode", "broad_up_long")).lower()
        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
        self.signal_times = tuple(parse_time(value) for value in params.get("signal_times", ["10:00:00"]))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_sector_count = int(params.get("min_sector_count", 4))
        self.min_open_gap = float(params.get("min_open_gap", 0.0))
        self.min_relative_gap = float(params.get("min_relative_gap", 0.0))
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
        decision = self._direction_from_features(row, state)
        if decision is None:
            return None
        direction, breadth_label = decision

        flow = self._confirmation_flow(state, direction)
        if flow is None:
            return None
        signed_volume, flow_volume, imbalance = flow

        state["signaled"] = True
        close = float(bar["close"])
        high = float(bar["high"])
        low = float(bar["low"])
        report_fields = {
            "academic_source_key": "market_breadth_moskowitz_1999_cont_2014",
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "feature_observation_date": row.get("feature_observation_date", ""),
            "feature_available_time": row.get("feature_available_time", ""),
            "setup_mode": self.setup_mode,
            "breadth_label": breadth_label,
            "flow_mode": self.flow_mode,
            "sector_up_count_7": row.get("sector_up_count_7"),
            "sector_down_count_7": row.get("sector_down_count_7"),
            "sector_avg_open_gap_7": row.get("sector_avg_open_gap_7"),
            "cyclical_up_count_4": row.get("cyclical_up_count_4"),
            "cyclical_down_count_4": row.get("cyclical_down_count_4"),
            "cyclical_avg_open_gap_4": row.get("cyclical_avg_open_gap_4"),
            "defensive_avg_open_gap_3": row.get("defensive_avg_open_gap_3"),
            "cyclical_minus_defensive_open_gap": row.get("cyclical_minus_defensive_open_gap"),
            "min_sector_count": self.min_sector_count,
            "min_open_gap": self.min_open_gap,
            "min_relative_gap": self.min_relative_gap,
            "session_open": state["session_open"],
            "confirmation_close": close,
            "confirmation_high": high,
            "confirmation_low": low,
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
            level_type=f"sector_opening_breadth_{breadth_label}_{direction}",
            swept_level=float(state["session_open"]),
            sweep_timestamp=pd.Timestamp(bar["timestamp"]),
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "breadth_label": breadth_label,
                "flow_mode": self.flow_mode,
                "orderflow_imbalance": imbalance,
                "es_move_ticks": state["move_ticks"],
                "target_r_multiple": self.params.get("target_r_multiple"),
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

    def _direction_from_features(self, row: dict, state: dict) -> tuple[str, str] | None:
        move_ticks = _finite_float(state.get("move_ticks"))
        if move_ticks is None:
            return None
        if self.setup_mode == "broad_up_long":
            if self._broad_up(row) and move_ticks >= self.min_es_move_ticks:
                return "long", "broad_up"
            return None
        if self.setup_mode == "broad_down_short":
            if self._broad_down(row) and move_ticks <= -self.min_es_move_ticks:
                return "short", "broad_down"
            return None
        if self.setup_mode == "cyclical_up_long":
            cyc_count = _finite_float(row.get("cyclical_up_count_4"))
            cyc_gap = _finite_float(row.get("cyclical_avg_open_gap_4"))
            if (
                cyc_count is not None
                and cyc_gap is not None
                and cyc_count >= self.min_sector_count
                and cyc_gap >= self.min_open_gap
                and move_ticks >= self.min_es_move_ticks
            ):
                return "long", "cyclical_up"
            return None
        if self.setup_mode == "riskoff_cycdown_short":
            cyc_count = _finite_float(row.get("cyclical_down_count_4"))
            cyc_gap = _finite_float(row.get("cyclical_avg_open_gap_4"))
            def_gap = _finite_float(row.get("defensive_avg_open_gap_3"))
            if (
                cyc_count is not None
                and cyc_gap is not None
                and def_gap is not None
                and cyc_count >= self.min_sector_count
                and def_gap - cyc_gap >= self.min_relative_gap
                and move_ticks <= -self.min_es_move_ticks
            ):
                return "short", "riskoff_cycdown"
            return None
        if self.setup_mode == "broad_two_sided":
            if self._broad_up(row) and move_ticks >= self.min_es_move_ticks:
                return "long", "broad_up"
            if self._broad_down(row) and move_ticks <= -self.min_es_move_ticks:
                return "short", "broad_down"
            return None
        raise ValueError(f"Unsupported setup_mode: {self.setup_mode}")

    def _broad_up(self, row: dict) -> bool:
        count = _finite_float(row.get("sector_up_count_7"))
        gap = _finite_float(row.get("sector_avg_open_gap_7"))
        return count is not None and gap is not None and count >= self.min_sector_count and gap >= self.min_open_gap

    def _broad_down(self, row: dict) -> bool:
        count = _finite_float(row.get("sector_down_count_7"))
        gap = _finite_float(row.get("sector_avg_open_gap_7"))
        return count is not None and gap is not None and count >= self.min_sector_count and gap <= -self.min_open_gap

    def _confirmation_flow(self, state: dict, direction: str) -> tuple[float, float, float] | None:
        signed_col, total_col = self._FLOW_COLUMNS[self.flow_mode]
        signed_volume = _finite_float(state.get(signed_col))
        total_volume = _finite_float(state.get(total_col))
        if signed_volume is None or total_volume is None or total_volume <= 0:
            return None
        if total_volume < self.min_flow_volume:
            return None
        imbalance = signed_volume / total_volume
        if not math.isfinite(imbalance):
            return None
        if direction == "long" and imbalance < self.min_orderflow_imbalance:
            return None
        if direction == "short" and imbalance > -self.min_orderflow_imbalance:
            return None
        return signed_volume, total_volume, imbalance

    def _validate(self) -> None:
        if self.setup_mode not in {
            "broad_up_long",
            "broad_down_short",
            "cyclical_up_long",
            "riskoff_cycdown_short",
            "broad_two_sided",
        }:
            raise ValueError("entry.params.setup_mode is unsupported.")
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError(f"entry.params.flow_mode must be one of {sorted(self._FLOW_COLUMNS)}.")
        if not self.signal_times:
            raise ValueError("entry.params.signal_times must define at least one signal time.")
        if self.bar_interval_minutes <= 0 or self.tick_size <= 0:
            raise ValueError("entry.params.bar_interval_minutes and tick_size must be greater than zero.")
        if self.min_sector_count < 1 or self.max_trades_per_day < 1:
            raise ValueError("entry.params count limits must be positive.")
        if self.min_open_gap < 0 or self.min_relative_gap < 0:
            raise ValueError("entry.params open-gap thresholds must be non-negative.")
        if self.min_es_move_ticks < 0 or self.min_orderflow_imbalance < 0 or self.min_flow_volume < 0:
            raise ValueError("entry.params confirmation thresholds must be non-negative.")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Sector opening-breadth feature CSV not found: {path}")
    out: dict[date, dict[str, float | str]] = {}
    string_columns = {"feature_observation_date", "feature_available_time"}
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
