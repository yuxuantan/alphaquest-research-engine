from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class CboeImpliedCorrelationOrderflowConfirmationEntry:
    name = "cboe_implied_correlation_orderflow_confirmation"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "high_short_term_correlation_short")).lower()
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/nq_cboe_implied_correlation_features_20110103_20260612.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.availability_market = str(params.get("availability_market", "NQ"))
        self.confirmation_mode = str(params.get("confirmation_mode", "flow_only")).lower()
        self.direction = str(params.get("direction", self._inferred_direction())).lower()
        self.flow_mode = str(params.get("flow_mode", "signed_imbalance")).lower()
        self.rth_start = parse_time(params.get("rth_start", "09:30:00"))
        self.signal_time = parse_time(params.get("signal_time", "13:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.correlation_rank_min = float(params.get("correlation_rank_min", 0.6))
        self.correlation_rank_max = float(params.get("correlation_rank_max", 0.4))
        self.correlation_change_rank_min = float(params.get("correlation_change_rank_min", 0.6))
        self.correlation_change_rank_max = float(params.get("correlation_change_rank_max", 0.4))
        self.term_spread_rank_min = float(params.get("term_spread_rank_min", 0.6))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.0025))
        self.min_confirm_return_ticks = float(params.get("min_confirm_return_ticks", 0))
        self.min_vwap_extension_ticks = float(params.get("min_vwap_extension_ticks", 0))
        self.stop_pct = float(params.get("stop_pct", 0.004))
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

        signal_timestamp = _session_timestamp(timestamp, self.signal_time)
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if state["signaled"] or bar_close != signal_timestamp:
            return None

        row = self.features.get(session_date)
        if row is None:
            return None
        state_direction, driver_column, driver_value = self._signal_direction(row)
        if state_direction is None or state_direction != self.direction:
            return None

        observed = self._observed_values(state, bar)
        if not self._matches(observed):
            return None

        state["signaled"] = True
        report_fields = {
            "academic_source_key": "driessen_maenhout_vilkov_correlation_risk_with_nq_orderflow",
            "setup_mode": self.setup_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": session_date.isoformat(),
            "cboe_observation_date": row.get("observation_date"),
            "availability_rule": (
                "latest Cboe implied-correlation close strictly before "
                f"{self.availability_market} session_date"
            ),
            "confirmation_mode": self.confirmation_mode,
            "flow_mode": self.flow_mode,
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "correlation_driver_column": driver_column,
            "correlation_driver_value": driver_value,
            "correlation_rank_min": self.correlation_rank_min,
            "correlation_rank_max": self.correlation_rank_max,
            "correlation_change_rank_min": self.correlation_change_rank_min,
            "correlation_change_rank_max": self.correlation_change_rank_max,
            "term_spread_rank_min": self.term_spread_rank_min,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "min_confirm_return_ticks": self.min_confirm_return_ticks,
            "min_vwap_extension_ticks": self.min_vwap_extension_ticks,
            "cor1m_close": row.get("cor1m_close"),
            "cor3m_close": row.get("cor3m_close"),
            "cor3m_change_1d": row.get("cor3m_change_1d"),
            "cor3m_change_5d": row.get("cor3m_change_5d"),
            "cor1m_minus_cor3m": row.get("cor1m_minus_cor3m"),
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            **observed,
        }
        return Signal(
            direction=self.direction,
            level_type=f"cboe_implied_correlation_orderflow_{self.setup_mode}",
            swept_level=float(bar["close"]),
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "confirmation_mode": self.confirmation_mode,
                "flow_mode": self.flow_mode,
                "correlation_driver_column": driver_column,
                "correlation_driver_value": driver_value,
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

    def _signal_direction(self, row: dict[str, float | str]) -> tuple[str | None, str, float]:
        if self.setup_mode == "high_cor3m_short":
            column = "cor3m_close_rank_252"
            return self._if_rank(column, _finite_float(row.get(column)), ">=", self.correlation_rank_min, "short")
        if self.setup_mode == "low_cor3m_long":
            column = "cor3m_close_rank_252"
            return self._if_rank(column, _finite_float(row.get(column)), "<=", self.correlation_rank_max, "long")
        if self.setup_mode == "rising_cor3m_short":
            column = "cor3m_change_1d_rank_252"
            return self._if_rank(
                column, _finite_float(row.get(column)), ">=", self.correlation_change_rank_min, "short"
            )
        if self.setup_mode == "falling_cor3m_long":
            column = "cor3m_change_1d_rank_252"
            return self._if_rank(
                column, _finite_float(row.get(column)), "<=", self.correlation_change_rank_max, "long"
            )
        if self.setup_mode == "high_short_term_correlation_short":
            column = "cor1m_minus_cor3m_rank_252"
            return self._if_rank(column, _finite_float(row.get(column)), ">=", self.term_spread_rank_min, "short")
        raise ValueError(
            f"Unsupported setup_mode for cboe_implied_correlation_orderflow_confirmation: {self.setup_mode}"
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
        open_ = _finite_float(state.get("session_open"))
        session_return_ticks = (
            (close - open_) / self.tick_size
            if close is not None and open_ is not None and self.tick_size > 0
            else math.nan
        )
        session_vwap = (
            state["cum_pv"] / state["cum_volume"] if state["cum_volume"] > 0 else math.nan
        )
        price_vs_vwap_ticks = (
            (close - session_vwap) / self.tick_size
            if close is not None and math.isfinite(session_vwap) and self.tick_size > 0
            else math.nan
        )
        signed_mult = 1.0 if self.direction == "long" else -1.0
        primary, secondary = self._flow_values(state)
        return {
            "session_open": open_,
            "session_close": close,
            "session_return_ticks": session_return_ticks,
            "signed_session_return_ticks": signed_mult * session_return_ticks,
            "session_vwap": session_vwap,
            "price_vs_vwap_ticks": price_vs_vwap_ticks,
            "signed_price_vs_vwap_ticks": signed_mult * price_vs_vwap_ticks,
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
        if self.confirmation_mode == "flow_only":
            return True
        if self.confirmation_mode in {"return_and_flow", "trend_continuation"}:
            return observed["signed_session_return_ticks"] >= self.min_confirm_return_ticks
        if self.confirmation_mode == "vwap_pressure":
            return observed["signed_price_vs_vwap_ticks"] >= self.min_vwap_extension_ticks
        raise ValueError("confirmation_mode must be flow_only, return_and_flow, or vwap_pressure.")

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
            "flow_mode must be signed_imbalance, large10_imbalance, large20_imbalance, or signed_and_large20."
        )

    def _inferred_direction(self) -> str:
        if self.setup_mode.endswith("_long"):
            return "long"
        return "short"

    def _validate(self) -> None:
        if self.direction not in {"long", "short"}:
            raise ValueError("direction must be long or short.")
        if self.setup_mode.endswith(("_long", "_short")) and self.direction != self._inferred_direction():
            raise ValueError(f"direction {self.direction} conflicts with setup_mode {self.setup_mode}.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("min_orderflow_imbalance must be non-negative.")
        for name, value in {
            "correlation_rank_min": self.correlation_rank_min,
            "correlation_rank_max": self.correlation_rank_max,
            "correlation_change_rank_min": self.correlation_change_rank_min,
            "correlation_change_rank_max": self.correlation_change_rank_max,
            "term_spread_rank_min": self.term_spread_rank_min,
        }.items():
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1].")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Cboe implied-correlation feature CSV not found: {path}")
    out: dict[date, dict[str, float | str]] = {}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            session_date = date.fromisoformat(str(row["session_date"]))
            out[session_date] = {
                key: (value if key == "observation_date" else _nan_float(value))
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
