from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.target_rr import MIN_TARGET_R_MULTIPLE
from alphaquest.utils.time import parse_time


class ImportExportPricePressureEntry:
    name = "import_export_price_pressure"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "core_import_relief_pullback_long")).lower()
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/es_import_export_price_pressure_features_20110103_20260609.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.entry_time = parse_time(params.get("entry_time", "11:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.macro_rank_min = float(params.get("macro_rank_min", 0.65))
        self.macro_rank_max = float(params.get("macro_rank_max", 0.35))
        self.min_session_return_bps = float(params.get("min_session_return_bps", 0.0))
        self.flow_column = str(params.get("flow_column", "signed_volume"))
        self.min_cumulative_flow = float(params.get("min_cumulative_flow", 0.0))
        self.stop_pct = float(params.get("stop_pct", 0.0025))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.5))
        self.state_by_day: dict[date, dict] = {}

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._validate()
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _date(bar["session_date"])
        state = self.state_by_day.setdefault(
            session_date,
            {"signaled": False, "rth_open": _finite_float(bar.get("open")), "cum_flow": 0.0},
        )
        if state["rth_open"] is None:
            state["rth_open"] = _finite_float(bar.get("open"))
        flow_value = _finite_float(bar.get(self.flow_column))
        if flow_value is None:
            return None
        state["cum_flow"] += flow_value
        if state["signaled"]:
            return None

        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        signal_timestamp = timestamp.replace(
            hour=self.entry_time.hour,
            minute=self.entry_time.minute,
            second=self.entry_time.second,
            microsecond=0,
        )
        if bar_close != signal_timestamp:
            return None

        row = self.features.get(session_date)
        if row is None:
            return None
        direction, driver_column, driver_value, confirmation_mode = self._signal_direction(row, bar, state)
        if direction is None:
            return None

        current_close = float(bar["close"])
        rth_open = float(state["rth_open"])
        session_return_bps = (current_close / rth_open - 1.0) * 10000.0 if rth_open else float("nan")
        report_fields = {
            "academic_source_key": "import_export_price_inflation_pressure_state",
            "setup_mode": self.setup_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "feature_observation_date": row.get("observation_date"),
            "feature_availability_date": row.get("availability_date"),
            "availability_lag_calendar_days_after_month": row.get(
                "availability_lag_calendar_days_after_month"
            ),
            "availability_rule": "monthly observation date plus conservative configured calendar-day lag",
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "macro_driver_column": driver_column,
            "macro_driver_value": driver_value,
            "macro_rank_min": self.macro_rank_min,
            "macro_rank_max": self.macro_rank_max,
            "confirmation_mode": confirmation_mode,
            "min_session_return_bps": self.min_session_return_bps,
            "session_return_bps": session_return_bps,
            "flow_column": self.flow_column,
            "cumulative_flow_to_signal": float(state["cum_flow"]),
            "min_cumulative_flow": self.min_cumulative_flow,
            "import_all_mom3": row.get("import_all_mom3"),
            "import_exfuel_mom3": row.get("import_exfuel_mom3"),
            "export_all_mom3": row.get("export_all_mom3"),
            "core_vs_headline_mom3": row.get("core_vs_headline_mom3"),
            "import_vs_export_mom3": row.get("import_vs_export_mom3"),
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"import_export_price_pressure_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "macro_driver_column": driver_column,
                "macro_driver_value": driver_value,
                "confirmation_mode": confirmation_mode,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _signal_direction(self, row: dict[str, float | str], bar: pd.Series, state: dict):
        if self.setup_mode == "core_import_relief_pullback_long":
            return self._rank_and_confirm(
                row,
                bar,
                state,
                column="core_vs_headline_rank_120m",
                direction="long",
                rank_op="<=",
                threshold=self.macro_rank_max,
                confirmation_mode="long_pullback_absorption",
            )
        if self.setup_mode == "broad_import_pressure_short":
            return self._rank_and_confirm(
                row,
                bar,
                state,
                column="import_all_mom3_rank_120m",
                direction="short",
                rank_op=">=",
                threshold=self.macro_rank_min,
                confirmation_mode="short_weakness",
            )
        if self.setup_mode == "core_import_pressure_short":
            return self._rank_and_confirm(
                row,
                bar,
                state,
                column="core_vs_headline_rank_120m",
                direction="short",
                rank_op=">=",
                threshold=self.macro_rank_min,
                confirmation_mode="short_weakness",
            )
        if self.setup_mode == "export_demand_strength_long":
            return self._rank_and_confirm(
                row,
                bar,
                state,
                column="export_all_mom3_rank_120m",
                direction="long",
                rank_op=">=",
                threshold=self.macro_rank_min,
                confirmation_mode="long_strength",
            )
        if self.setup_mode == "terms_trade_pressure_short":
            return self._rank_and_confirm(
                row,
                bar,
                state,
                column="import_vs_export_rank_120m",
                direction="short",
                rank_op=">=",
                threshold=self.macro_rank_min,
                confirmation_mode="short_weakness",
            )
        if self.setup_mode == "disinflation_reclaim_long":
            return self._rank_and_confirm(
                row,
                bar,
                state,
                column="import_all_mom3_rank_120m",
                direction="long",
                rank_op="<=",
                threshold=self.macro_rank_max,
                confirmation_mode="long_strength",
            )
        raise ValueError(f"Unsupported setup_mode for import_export_price_pressure: {self.setup_mode}")

    def _rank_and_confirm(
        self,
        row: dict[str, float | str],
        bar: pd.Series,
        state: dict,
        *,
        column: str,
        direction: str,
        rank_op: str,
        threshold: float,
        confirmation_mode: str,
    ):
        rank = _finite_float(row.get(column))
        if rank is None:
            return None, column, float("nan"), confirmation_mode
        rank_passed = rank >= threshold if rank_op == ">=" else rank <= threshold
        if not rank_passed or not self._confirmation_passed(bar, state, confirmation_mode):
            return None, column, rank, confirmation_mode
        return direction, column, rank, confirmation_mode

    def _confirmation_passed(self, bar: pd.Series, state: dict, confirmation_mode: str) -> bool:
        rth_open = _finite_float(state.get("rth_open"))
        close = _finite_float(bar.get("close"))
        if rth_open is None or close is None or rth_open == 0:
            return False
        session_return_bps = (close / rth_open - 1.0) * 10000.0
        cum_flow = float(state.get("cum_flow", 0.0))
        if confirmation_mode == "long_strength":
            return session_return_bps >= self.min_session_return_bps and cum_flow >= self.min_cumulative_flow
        if confirmation_mode == "long_pullback_absorption":
            return session_return_bps <= -self.min_session_return_bps and cum_flow >= self.min_cumulative_flow
        if confirmation_mode == "short_weakness":
            return session_return_bps <= -self.min_session_return_bps and cum_flow <= -self.min_cumulative_flow
        raise ValueError(f"Unsupported confirmation_mode for import_export_price_pressure: {confirmation_mode}")

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        if self.stop_pct <= 0:
            raise ValueError("stop_pct must be greater than 0.")
        if self.target_r_multiple < MIN_TARGET_R_MULTIPLE:
            raise ValueError(f"target_r_multiple must be >= {MIN_TARGET_R_MULTIPLE:.1f} reward:risk.")
        for name, value in {
            "macro_rank_min": self.macro_rank_min,
            "macro_rank_max": self.macro_rank_max,
        }.items():
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1].")
        if self.min_session_return_bps < 0:
            raise ValueError("min_session_return_bps must be non-negative.")
        if self.min_cumulative_flow < 0:
            raise ValueError("min_cumulative_flow must be non-negative.")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Import/export price-pressure feature CSV not found: {path}")
    out: dict[date, dict[str, float | str]] = {}
    string_columns = {"observation_date", "availability_date"}
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
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
