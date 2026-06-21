from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class SectorRotationOrderflowPullbackEntry:
    name = "sector_rotation_orderflow_pullback"

    _FLOW_COLUMNS = {
        "signed_volume": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }

    _SECTOR_MODES = {
        "growth_risk_on_long": ("growth_minus_defensive_5d_rank_252", "high", "long"),
        "cyclical_risk_on_long": ("cyclical_minus_defensive_1d_rank_252", "high", "long"),
        "financial_industrial_risk_on_long": (
            "financial_industrial_minus_spy_1d_rank_252",
            "high",
            "long",
        ),
        "defensive_risk_off_short": ("cyclical_minus_defensive_1d_rank_252", "low", "short"),
        "defensive_persistent_short": ("cyclical_minus_defensive_5d_rank_252", "low", "short"),
    }

    def __init__(self, params: dict):
        self.params = params
        self.feature_csv = str(
            params.get(
                "feature_csv",
                "data/external/es_sector_rotation_features_20110103_20260609.csv",
            )
        )
        self.features = _load_features(self.feature_csv)
        self.sector_mode = str(params.get("sector_mode", "growth_risk_on_long")).lower()
        self.trigger_mode = str(params.get("trigger_mode", "vwap_reclaim")).lower()
        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
        self.start_time = parse_time(params.get("start_time", "10:00:00"))
        self.end_time = parse_time(params.get("end_time", "14:30:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.rank_threshold = float(params.get("rank_threshold", 0.60))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.02))
        self.min_flow_volume = float(params.get("min_flow_volume", 0.0))
        self.required_trend_closes = int(params.get("required_trend_closes", 2))
        self.trend_vwap_buffer_ticks = float(params.get("trend_vwap_buffer_ticks", 0.0))
        self.pullback_tolerance_ticks = float(params.get("pullback_tolerance_ticks", 1.0))
        self.reclaim_buffer_ticks = float(params.get("reclaim_buffer_ticks", 0.0))
        self.reclaim_window_bars = int(params.get("reclaim_window_bars", 3))
        self.fast_period = int(params.get("fast_period", 12))
        self.slow_period = int(params.get("slow_period", 36))
        self.min_ema_gap_ticks = float(params.get("min_ema_gap_ticks", 3.0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self._validate()
        self.state_by_day: dict = {}

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        session_date = _date(bar.get("session_date"))
        state = self.state_by_day.setdefault(session_date, self._new_state())
        close = _finite_float(bar.get("close"))
        if close is None:
            return None

        direction, sector_column, sector_rank = self._sector_direction(session_date)
        signal = None
        if direction is not None and not state["signaled"]:
            signal = self._signal_from_bar(bar, state, direction, sector_column, sector_rank)
            if signal is not None:
                state["signaled"] = True

        self._update_state(bar, state, close)
        return signal

    def _new_state(self) -> dict:
        return {
            "signaled": False,
            "long_trend_count": 0,
            "short_trend_count": 0,
            "long_pullback": None,
            "short_pullback": None,
            "fast_ema": None,
            "slow_ema": None,
            "ema_count": 0,
        }

    def _signal_from_bar(
        self,
        bar: pd.Series,
        state: dict,
        direction: str,
        sector_column: str,
        sector_rank: float,
    ) -> Signal | None:
        timestamp = pd.Timestamp(bar["timestamp"])
        signal_timestamp = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if signal_timestamp.time() < self.start_time or signal_timestamp.time() > self.end_time:
            return None

        if self.trigger_mode == "vwap_reclaim":
            setup = self._vwap_reclaim_setup(bar, state, direction)
        elif self.trigger_mode == "ema_pullback":
            setup = self._ema_pullback_setup(bar, state, direction)
        else:
            raise ValueError(f"Unsupported trigger_mode: {self.trigger_mode}")
        if setup is None:
            return None

        flow = self._confirmation_flow(bar, direction)
        if flow is None:
            return None
        signed_volume, flow_volume, imbalance = flow
        close = float(bar["close"])
        high = float(bar["high"])
        low = float(bar["low"])
        report_fields = {
            "academic_source_key": "moskowitz_grinblatt_1999_industry_momentum_cont_2014_ofi",
            "sector_mode": self.sector_mode,
            "trigger_mode": self.trigger_mode,
            "feature_csv": self.feature_csv,
            "feature_session_date": _date(bar.get("session_date")).isoformat(),
            "sector_column": sector_column,
            "sector_rank": sector_rank,
            "rank_threshold": self.rank_threshold,
            "flow_mode": self.flow_mode,
            "confirmation_signed_volume": signed_volume,
            "confirmation_flow_volume": flow_volume,
            "confirmation_orderflow_imbalance": imbalance,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "confirmation_close": close,
            "confirmation_high": high,
            "confirmation_low": low,
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            **setup,
        }
        return Signal(
            direction=direction,
            level_type=f"sector_rotation_orderflow_{self.trigger_mode}_{direction}",
            swept_level=float(setup["reference_level"]),
            sweep_timestamp=timestamp,
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=signal_timestamp,
            metadata={
                "sector_mode": self.sector_mode,
                "trigger_mode": self.trigger_mode,
                "sector_column": sector_column,
                "sector_rank": sector_rank,
                "rank_threshold": self.rank_threshold,
                "flow_mode": self.flow_mode,
                "orderflow_imbalance": imbalance,
                "min_orderflow_imbalance": self.min_orderflow_imbalance,
            },
            report_fields=report_fields,
        )

    def _vwap_reclaim_setup(self, bar: pd.Series, state: dict, direction: str) -> dict | None:
        vwap = _finite_float(bar.get("vwap"))
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        close = _finite_float(bar.get("close"))
        if None in {vwap, high, low, close}:
            return None
        trend_buffer = self.trend_vwap_buffer_ticks * self.tick_size
        pullback_tolerance = self.pullback_tolerance_ticks * self.tick_size
        reclaim_buffer = self.reclaim_buffer_ticks * self.tick_size
        if direction == "long":
            pullback = state.get("long_pullback")
            if pullback is None:
                return None
            if self._expired(bar, pullback):
                state["long_pullback"] = None
                return None
            if close < vwap + reclaim_buffer:
                return None
            state["long_pullback"] = None
            return {
                "reference_type": "vwap",
                "reference_level": vwap,
                "trend_count": state["long_trend_count"],
                "trend_buffer_ticks": self.trend_vwap_buffer_ticks,
                "pullback_tolerance_ticks": self.pullback_tolerance_ticks,
                "reclaim_buffer_ticks": self.reclaim_buffer_ticks,
                "pullback_timestamp": pullback["timestamp"],
                "pullback_low": min(float(pullback["pullback_low"]), low),
                "pullback_high": max(float(pullback["pullback_high"]), high),
            }
        pullback = state.get("short_pullback")
        if pullback is None:
            return None
        if self._expired(bar, pullback):
            state["short_pullback"] = None
            return None
        if close > vwap - reclaim_buffer:
            return None
        state["short_pullback"] = None
        return {
            "reference_type": "vwap",
            "reference_level": vwap,
            "trend_count": state["short_trend_count"],
            "trend_buffer_ticks": self.trend_vwap_buffer_ticks,
            "pullback_tolerance_ticks": self.pullback_tolerance_ticks,
            "reclaim_buffer_ticks": self.reclaim_buffer_ticks,
            "pullback_timestamp": pullback["timestamp"],
            "pullback_low": min(float(pullback["pullback_low"]), low),
            "pullback_high": max(float(pullback["pullback_high"]), high),
        }

    def _ema_pullback_setup(self, bar: pd.Series, state: dict, direction: str) -> dict | None:
        prior_fast = _finite_float(state.get("fast_ema"))
        prior_slow = _finite_float(state.get("slow_ema"))
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        close = _finite_float(bar.get("close"))
        open_ = _finite_float(bar.get("open"))
        if None in {prior_fast, prior_slow, high, low, close, open_}:
            return None
        if state["ema_count"] < self.slow_period:
            return None
        tolerance = self.pullback_tolerance_ticks * self.tick_size
        if direction == "long":
            gap_ticks = (prior_fast - prior_slow) / self.tick_size
            if gap_ticks < self.min_ema_gap_ticks:
                return None
            if not (low <= prior_fast + tolerance and close > prior_fast and close > open_):
                return None
        else:
            gap_ticks = (prior_slow - prior_fast) / self.tick_size
            if gap_ticks < self.min_ema_gap_ticks:
                return None
            if not (high >= prior_fast - tolerance and close < prior_fast and close < open_):
                return None
        return {
            "reference_type": "fast_ema",
            "reference_level": prior_fast,
            "slow_reference_level": prior_slow,
            "ema_gap_ticks": gap_ticks,
            "min_ema_gap_ticks": self.min_ema_gap_ticks,
            "pullback_tolerance_ticks": self.pullback_tolerance_ticks,
        }

    def _update_state(self, bar: pd.Series, state: dict, close: float) -> None:
        vwap = _finite_float(bar.get("vwap"))
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        if vwap is not None and high is not None and low is not None:
            trend_buffer = self.trend_vwap_buffer_ticks * self.tick_size
            pullback_tolerance = self.pullback_tolerance_ticks * self.tick_size
            if close >= vwap + trend_buffer:
                state["long_trend_count"] += 1
            else:
                state["long_trend_count"] = 0
            if close <= vwap - trend_buffer:
                state["short_trend_count"] += 1
            else:
                state["short_trend_count"] = 0

            idx = int(bar.name) if bar.name is not None else 0
            if state["long_trend_count"] >= self.required_trend_closes and low <= vwap + pullback_tolerance:
                state["long_pullback"] = self._pullback_state(idx, bar)
            if state["short_trend_count"] >= self.required_trend_closes and high >= vwap - pullback_tolerance:
                state["short_pullback"] = self._pullback_state(idx, bar)

        state["fast_ema"] = _ema_update(state.get("fast_ema"), close, self.fast_period)
        state["slow_ema"] = _ema_update(state.get("slow_ema"), close, self.slow_period)
        state["ema_count"] += 1

    def _confirmation_flow(self, bar: pd.Series, direction: str) -> tuple[float, float, float] | None:
        signed_col, total_col = self._FLOW_COLUMNS[self.flow_mode]
        signed_volume = _finite_float(bar.get(signed_col))
        total_volume = _finite_float(bar.get(total_col))
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

    def _sector_direction(self, session_date: date) -> tuple[str | None, str, float]:
        row = self.features.get(session_date)
        if row is None:
            return None, "", float("nan")
        column, tail, direction = self._SECTOR_MODES[self.sector_mode]
        rank = _finite_float(row.get(column))
        if rank is None:
            return None, column, float("nan")
        if tail == "high" and rank >= self.rank_threshold:
            return direction, column, rank
        if tail == "low" and rank <= 1.0 - self.rank_threshold:
            return direction, column, rank
        return None, column, rank

    @staticmethod
    def _pullback_state(idx: int, bar: pd.Series) -> dict:
        return {
            "idx": idx,
            "timestamp": bar["timestamp"],
            "pullback_low": float(bar["low"]),
            "pullback_high": float(bar["high"]),
        }

    def _expired(self, bar: pd.Series, pullback: dict) -> bool:
        idx = int(bar.name) if bar.name is not None else 0
        bars_between = max(0, idx - int(pullback["idx"]) - 1)
        return bars_between > self.reclaim_window_bars

    def _validate(self) -> None:
        if self.sector_mode not in self._SECTOR_MODES:
            raise ValueError(f"entry.params.sector_mode must be one of {sorted(self._SECTOR_MODES)}.")
        if self.trigger_mode not in {"vwap_reclaim", "ema_pullback"}:
            raise ValueError("entry.params.trigger_mode must be vwap_reclaim or ema_pullback.")
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError(f"entry.params.flow_mode must be one of {sorted(self._FLOW_COLUMNS)}.")
        if self.end_time <= self.start_time:
            raise ValueError("entry.params.end_time must be after start_time.")
        if self.bar_interval_minutes <= 0 or self.tick_size <= 0:
            raise ValueError("entry.params.bar_interval_minutes and tick_size must be greater than zero.")
        if not 0.0 < self.rank_threshold <= 1.0:
            raise ValueError("entry.params.rank_threshold must be in (0, 1].")
        if self.min_orderflow_imbalance < 0 or self.min_flow_volume < 0:
            raise ValueError("entry.params orderflow thresholds must be non-negative.")
        if self.required_trend_closes < 1 or self.reclaim_window_bars < 0 or self.max_trades_per_day < 1:
            raise ValueError("entry.params count limits must be positive.")
        if self.fast_period <= 1 or self.slow_period <= 1 or self.fast_period >= self.slow_period:
            raise ValueError("entry.params.fast_period must be > 1 and less than slow_period.")


def _load_features(path: str) -> dict[date, dict[str, float | str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Sector-rotation feature CSV not found: {path}")
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


def _date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


def _ema_update(previous: float | None, close: float, period: int) -> float:
    if previous is None or pd.isna(previous):
        return close
    alpha = 2.0 / (period + 1.0)
    return previous + alpha * (close - previous)


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
