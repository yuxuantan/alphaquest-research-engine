from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class NqTechRelativeOrderflowConfirmationEntry:
    name = "nq_tech_relative_orderflow_confirmation"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "tech_5d_nonleadership_short")).lower()
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/nq_tech_relative_strength_features_20110103_20260612.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.confirmation_mode = str(params.get("confirmation_mode", "return_and_flow")).lower()
        self.direction = str(params.get("direction", self._inferred_direction())).lower()
        self.flow_mode = str(params.get("flow_mode", "signed_imbalance")).lower()
        self.rth_start = parse_time(params.get("rth_start", "09:30:00"))
        self.signal_time = parse_time(params.get("signal_time", "11:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:15:00"))
        self.bounce_window_end = parse_time(params.get("bounce_window_end", "10:00:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.rank_min = float(params.get("rank_min", 0.60))
        self.rank_max = float(params.get("rank_max", 0.40))
        self.volume_rank_min = float(params.get("volume_rank_min", 0.60))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.02))
        self.min_confirm_return_ticks = float(params.get("min_confirm_return_ticks", 8))
        self.min_vwap_extension_ticks = float(params.get("min_vwap_extension_ticks", 8))
        self.min_bounce_return_ticks = float(params.get("min_bounce_return_ticks", 8))
        self.opening_range_minutes = int(params.get("opening_range_minutes", 60))
        self.stop_pct = float(params.get("stop_pct", 0.005))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.5))
        self.state_by_day: dict[date, dict] = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _date(bar["session_date"])
        state = self._state(session_date, bar)
        self._update_state(state, bar)

        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if bar_close == _session_timestamp(timestamp, self.bounce_window_end):
            state["bounce_return_ticks"] = self._session_return_ticks(state, bar)
        if bar_close <= _session_timestamp(timestamp, self.rth_start) + pd.Timedelta(
            minutes=self.opening_range_minutes
        ):
            state["opening_range_high"] = max(state["opening_range_high"], float(bar["high"]))
            state["opening_range_low"] = min(state["opening_range_low"], float(bar["low"]))

        signal_timestamp = _session_timestamp(timestamp, self.signal_time)
        if state["signaled"] or bar_close != signal_timestamp:
            return None

        feature_row = self.features.get(session_date)
        if feature_row is None:
            return None
        state_direction, driver_column, driver_value = self._state_signal(feature_row)
        if state_direction is None or state_direction != self.direction:
            return None

        observed = self._observed_values(state, bar)
        if not self._matches(observed):
            return None

        state["signaled"] = True
        current_close = float(bar["close"])
        report_fields = {
            "academic_source_key": (
                "moskowitz_grinblatt_1999_industry_momentum_"
                "hong_torous_valkanov_2007_industry_leads_with_nq_orderflow"
            ),
            "setup_mode": self.setup_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "tech_observation_date": feature_row.get("observation_date"),
            "availability_cutoff": feature_row.get("availability_cutoff"),
            "availability_lag_business_days": feature_row.get("availability_lag_business_days"),
            "availability_rule": (
                "latest XLK and SPY daily close on or before "
                "NQ session_date minus one business day"
            ),
            "confirmation_mode": self.confirmation_mode,
            "flow_mode": self.flow_mode,
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "tech_driver_column": driver_column,
            "tech_driver_value": driver_value,
            "rank_min": self.rank_min,
            "rank_max": self.rank_max,
            "volume_rank_min": self.volume_rank_min,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "min_confirm_return_ticks": self.min_confirm_return_ticks,
            "min_vwap_extension_ticks": self.min_vwap_extension_ticks,
            "min_bounce_return_ticks": self.min_bounce_return_ticks,
            "xlk_minus_spy_1d": feature_row.get("xlk_minus_spy_1d"),
            "xlk_minus_spy_5d": feature_row.get("xlk_minus_spy_5d"),
            "xlk_volume_ratio_20": feature_row.get("xlk_volume_ratio_20"),
            "xlk_attention_pressure_1d": feature_row.get("xlk_attention_pressure_1d"),
            "xlk_minus_spy_1d_rank_252": feature_row.get("xlk_minus_spy_1d_rank_252"),
            "xlk_minus_spy_5d_rank_252": feature_row.get("xlk_minus_spy_5d_rank_252"),
            "xlk_volume_ratio_20_rank_252": feature_row.get("xlk_volume_ratio_20_rank_252"),
            "xlk_attention_pressure_1d_rank_252": feature_row.get(
                "xlk_attention_pressure_1d_rank_252"
            ),
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            **observed,
        }
        return Signal(
            direction=self.direction,
            level_type=f"nq_tech_relative_orderflow_confirmation_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "confirmation_mode": self.confirmation_mode,
                "flow_mode": self.flow_mode,
                "tech_driver_column": driver_column,
                "tech_driver_value": driver_value,
                "confirmation_orderflow_imbalance": observed["primary_orderflow_imbalance"],
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _state(self, session_date: date, bar: pd.Series) -> dict:
        state = self.state_by_day.get(session_date)
        if state is not None:
            return state
        state = {
            "signaled": False,
            "session_open": _finite_float(bar.get("open")),
            "cum_pv": 0.0,
            "cum_volume": 0.0,
            "cum_signed_volume": 0.0,
            "cum_large10_volume": 0.0,
            "cum_large10_signed_volume": 0.0,
            "cum_large20_volume": 0.0,
            "cum_large20_signed_volume": 0.0,
            "opening_range_high": float(bar["high"]),
            "opening_range_low": float(bar["low"]),
            "bounce_return_ticks": math.nan,
        }
        self.state_by_day[session_date] = state
        return state

    def _update_state(self, state: dict, bar: pd.Series) -> None:
        close = _finite_float(bar.get("close"))
        volume = max(_finite_float(bar.get("volume")) or 0.0, 0.0)
        if close is not None and volume > 0:
            state["cum_pv"] += close * volume
            state["cum_volume"] += volume
        for column in [
            "signed_volume",
            "large10_volume",
            "large10_signed_volume",
            "large20_volume",
            "large20_signed_volume",
        ]:
            state[f"cum_{column}"] += _finite_float(bar.get(column)) or 0.0

    def _state_signal(self, row: dict[str, float | str]) -> tuple[str | None, str, float]:
        if self.setup_mode == "tech_1d_strength_long":
            column = "xlk_minus_spy_1d_rank_252"
            return self._if_rank(column, _finite_float(row.get(column)), ">=", self.rank_min, "long")
        if self.setup_mode == "tech_5d_strength_long":
            column = "xlk_minus_spy_5d_rank_252"
            return self._if_rank(column, _finite_float(row.get(column)), ">=", self.rank_min, "long")
        if self.setup_mode in {"tech_1d_weakness_short", "tech_1d_nonleadership_short"}:
            column = "xlk_minus_spy_1d_rank_252"
            return self._if_rank(column, _finite_float(row.get(column)), "<=", self.rank_max, "short")
        if self.setup_mode in {"tech_5d_weakness_short", "tech_5d_nonleadership_short"}:
            column = "xlk_minus_spy_5d_rank_252"
            return self._if_rank(column, _finite_float(row.get(column)), "<=", self.rank_max, "short")
        if self.setup_mode == "tech_attention_strength_long":
            strength_column = "xlk_attention_pressure_1d_rank_252"
            volume_column = "xlk_volume_ratio_20_rank_252"
            strength_rank = _finite_float(row.get(strength_column))
            volume_rank = _finite_float(row.get(volume_column))
            if strength_rank is None or volume_rank is None:
                return None, strength_column, float("nan")
            if strength_rank >= self.rank_min and volume_rank >= self.volume_rank_min:
                return "long", strength_column, strength_rank
            return None, strength_column, strength_rank
        raise ValueError(
            f"Unsupported setup_mode for nq_tech_relative_orderflow_confirmation: {self.setup_mode}"
        )

    @staticmethod
    def _if_rank(column: str, rank: float | None, op: str, threshold: float, direction: str):
        if rank is None:
            return None, column, float("nan")
        if op == ">=":
            return (direction if rank >= threshold else None), column, rank
        return (direction if rank <= threshold else None), column, rank

    def _observed_values(self, state: dict, bar: pd.Series) -> dict:
        close = _finite_float(bar.get("close"))
        session_return_ticks = self._session_return_ticks(state, bar)
        session_vwap = (
            state["cum_pv"] / state["cum_volume"] if state["cum_volume"] > 0 else math.nan
        )
        price_vs_vwap_ticks = (
            (close - session_vwap) / self.tick_size
            if close is not None and math.isfinite(session_vwap) and self.tick_size > 0
            else math.nan
        )
        opening_break_ticks = self._opening_break_ticks(state, close)
        signed_mult = 1.0 if self.direction == "long" else -1.0
        primary, secondary = self._flow_values(state)
        return {
            "session_open": state["session_open"],
            "session_close": close,
            "session_return_ticks": session_return_ticks,
            "signed_session_return_ticks": signed_mult * session_return_ticks,
            "session_vwap": session_vwap,
            "price_vs_vwap_ticks": price_vs_vwap_ticks,
            "signed_price_vs_vwap_ticks": signed_mult * price_vs_vwap_ticks,
            "opening_range_high": state["opening_range_high"],
            "opening_range_low": state["opening_range_low"],
            "opening_break_ticks": opening_break_ticks,
            "signed_opening_break_ticks": signed_mult * opening_break_ticks,
            "bounce_return_ticks": state["bounce_return_ticks"],
            "signed_bounce_return_ticks": signed_mult * state["bounce_return_ticks"],
            "primary_orderflow_imbalance": primary,
            "secondary_orderflow_imbalance": secondary,
            "signed_primary_orderflow_imbalance": signed_mult * primary if primary is not None else math.nan,
            "signed_secondary_orderflow_imbalance": (
                signed_mult * secondary if secondary is not None else math.nan
            ),
        }

    def _matches(self, observed: dict) -> bool:
        primary = observed["signed_primary_orderflow_imbalance"]
        secondary = observed["signed_secondary_orderflow_imbalance"]
        flow_ok = (
            _finite(primary)
            and primary >= self.min_orderflow_imbalance
            and (not _finite(secondary) or secondary >= self.min_orderflow_imbalance)
        )
        if not flow_ok:
            return False

        if self.confirmation_mode in {"return_and_flow", "trend_continuation"}:
            return observed["signed_session_return_ticks"] >= self.min_confirm_return_ticks
        if self.confirmation_mode == "vwap_pressure":
            return observed["signed_price_vs_vwap_ticks"] >= self.min_vwap_extension_ticks
        if self.confirmation_mode == "failed_bounce":
            return (
                observed["signed_bounce_return_ticks"] <= -self.min_bounce_return_ticks
                and observed["signed_session_return_ticks"] >= self.min_confirm_return_ticks
            )
        if self.confirmation_mode == "opening_range_break":
            return observed["signed_opening_break_ticks"] >= self.min_confirm_return_ticks
        raise ValueError(
            "confirmation_mode must be return_and_flow, trend_continuation, "
            "vwap_pressure, failed_bounce, or opening_range_break."
        )

    def _session_return_ticks(self, state: dict, bar: pd.Series) -> float:
        close = _finite_float(bar.get("close"))
        open_ = _finite_float(state.get("session_open"))
        if close is None or open_ is None or self.tick_size <= 0:
            return math.nan
        return (close - open_) / self.tick_size

    def _opening_break_ticks(self, state: dict, close: float | None) -> float:
        if close is None:
            return math.nan
        if self.direction == "long":
            return (close - state["opening_range_high"]) / self.tick_size
        return (state["opening_range_low"] - close) / self.tick_size

    def _flow_values(self, state: dict) -> tuple[float | None, float | None]:
        signed = _ratio(state["cum_signed_volume"], state["cum_volume"])
        large10 = _ratio(state["cum_large10_signed_volume"], state["cum_large10_volume"])
        large20 = _ratio(state["cum_large20_signed_volume"], state["cum_large20_volume"])
        if self.flow_mode in {"signed_imbalance", "all_volume_imbalance"}:
            return signed, None
        if self.flow_mode in {"large10_imbalance", "large10"}:
            return large10, None
        if self.flow_mode in {"large20_imbalance", "large20"}:
            return large20, None
        if self.flow_mode in {"signed_and_large20", "broad_large_alignment"}:
            return signed, large20
        raise ValueError(
            "flow_mode must be signed_imbalance, large10_imbalance, "
            "large20_imbalance, or signed_and_large20."
        )

    def _inferred_direction(self) -> str:
        if self.setup_mode.endswith("_short"):
            return "short"
        if self.setup_mode.endswith("_long"):
            return "long"
        return "short"

    def _validate(self) -> None:
        if self.direction not in {"long", "short"}:
            raise ValueError("direction must be long or short.")
        expected_direction = self._inferred_direction()
        if self.setup_mode.endswith(("_long", "_short")) and self.direction != expected_direction:
            raise ValueError(
                f"direction {self.direction} conflicts with setup_mode {self.setup_mode}."
            )
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        for name, value in {
            "rank_min": self.rank_min,
            "rank_max": self.rank_max,
            "volume_rank_min": self.volume_rank_min,
        }.items():
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1].")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("min_orderflow_imbalance must be non-negative.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if self.opening_range_minutes <= 0:
            raise ValueError("opening_range_minutes must be greater than 0.")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"NQ tech relative strength feature CSV not found: {path}")
    out: dict[date, dict[str, float | str]] = {}
    string_columns = {"observation_date", "availability_cutoff"}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            session_date = date.fromisoformat(str(row["session_date"]))
            out[session_date] = {
                key: (value if key in string_columns else _nan_float(value))
                for key, value in row.items()
                if key != "session_date"
            }
    return out


def _session_timestamp(timestamp: pd.Timestamp, time_value) -> pd.Timestamp:
    return timestamp.replace(
        hour=time_value.hour,
        minute=time_value.minute,
        second=time_value.second,
        microsecond=0,
    )


def _date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


def _ratio(numerator, denominator) -> float | None:
    denominator = _finite_float(denominator)
    if denominator is None or denominator <= 0:
        return None
    numerator = _finite_float(numerator)
    if numerator is None:
        return None
    return numerator / denominator


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


def _finite(value) -> bool:
    return value is not None and math.isfinite(float(value))
