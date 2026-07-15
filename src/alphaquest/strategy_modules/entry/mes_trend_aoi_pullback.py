from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class MesTrendAoiPullbackEntry:
    name = "mes_trend_aoi_pullback"

    _MODES = {
        "market_aoi_pullback",
        "prior_extreme_pullback",
        "opening_range_pullback",
        "overnight_pullback",
        "value_area_pullback",
        "lvn_pullback",
        "profile_aoi_pullback",
        "all_aoi_pullback",
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "market_aoi_pullback")).lower()
        self.start_time = parse_time(params.get("start_time", "10:00:00"))
        self.end_time = parse_time(params.get("end_time", "15:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.opening_range_minutes = int(params.get("opening_range_minutes", 30))
        self.lookback_minutes = int(params.get("lookback_minutes", 15))
        self.trend_lookback_minutes = int(params.get("trend_lookback_minutes", 30))
        self.rank_window = int(params.get("rank_window", 252))
        self.share_mode = str(params.get("share_mode", "trade")).lower()
        self.min_share_rank = float(params.get("min_share_rank", 0.65))
        self.min_abs_return_ticks = float(params.get("min_abs_return_ticks", 4.0))
        self.min_trend_return_ticks = float(params.get("min_trend_return_ticks", 6.0))
        self.min_probe_ticks = float(params.get("min_probe_ticks", 1.0))
        self.confirmation_ticks = float(params.get("confirmation_ticks", 0.0))
        self.min_delta_imbalance = float(params.get("min_delta_imbalance", 0.0))
        self.require_footprint_absorption = bool(params.get("require_footprint_absorption", False))
        self.cached_profile_prefix = str(params.get("cached_profile_prefix", "prior_vap"))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.current_session = None
        self.current_session_bars: list[pd.Series] = []
        self.signaled_sessions: set = set()
        self.history_by_session: dict[object, dict[pd.Timestamp, float]] = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._roll_session(bar)
        if not bool(bar.get("is_rth", False)):
            return None

        session_date = bar.get("session_date")
        timestamp = pd.Timestamp(bar["timestamp"])
        signal_timestamp = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        self._append_history(session_date, signal_timestamp, bar)

        signal = None
        if session_date not in self.signaled_sessions and trades_today < self.max_trades_per_day:
            signal = self._signal_from_completed_bar(bar, signal_timestamp)
            if signal is not None:
                self.signaled_sessions.add(session_date)
        self.current_session_bars.append(bar.copy())
        return signal

    def _roll_session(self, bar: pd.Series) -> None:
        session_date = bar.get("session_date")
        if self.current_session is None:
            self.current_session = session_date
            return
        if session_date == self.current_session:
            return
        self.current_session = session_date
        self.current_session_bars = []

    def _append_history(self, session_date, bar_close: pd.Timestamp, bar: pd.Series) -> None:
        close = _finite_float(bar.get("close"))
        if close is None:
            return
        history = self.history_by_session.setdefault(session_date, {})
        history[bar_close] = close
        max_minutes = self.lookback_minutes + self.trend_lookback_minutes + 5
        cutoff = bar_close - pd.Timedelta(minutes=max_minutes)
        self.history_by_session[session_date] = {
            timestamp: value
            for timestamp, value in history.items()
            if timestamp >= cutoff
        }

    def _signal_from_completed_bar(self, bar: pd.Series, signal_timestamp: pd.Timestamp) -> Signal | None:
        if signal_timestamp.time() < self.start_time or signal_timestamp.time() > self.end_time:
            return None

        values = self._bar_values(bar)
        if values is None:
            return None
        metrics = self._mes_metrics(bar)
        if metrics is None or metrics["share_rank"] < self.min_share_rank:
            return None
        trend = self._trend_return_ticks(bar.get("session_date"), signal_timestamp)
        if trend is None:
            return None

        for direction, aoi_type, level in self._candidate_aois(bar):
            if direction == "long" and not self.allow_long:
                continue
            if direction == "short" and not self.allow_short:
                continue
            if not self._trend_and_pullback_match(direction, metrics, trend):
                continue
            if not self._aoi_reclaim_confirms(direction, bar, values, level):
                continue
            return self._signal(direction, aoi_type, level, bar, values, metrics, trend, signal_timestamp)
        return None

    def _candidate_aois(self, bar: pd.Series) -> list[tuple[str, str, float]]:
        candidates: list[tuple[str, str, float]] = []
        mode = self.setup_mode
        if mode in {"prior_extreme_pullback", "market_aoi_pullback", "all_aoi_pullback"}:
            self._append_candidate(candidates, "long", "prior_rth_low", bar.get("prev_rth_low"))
            self._append_candidate(candidates, "short", "prior_rth_high", bar.get("prev_rth_high"))
        if mode in {"opening_range_pullback", "market_aoi_pullback", "all_aoi_pullback"}:
            opening = self._opening_range()
            if opening is not None:
                candidates.append(("long", "opening_range_low", opening["low"]))
                candidates.append(("short", "opening_range_high", opening["high"]))
        if mode in {"overnight_pullback", "market_aoi_pullback", "all_aoi_pullback"}:
            self._append_candidate(candidates, "long", "overnight_low", bar.get("overnight_low"))
            self._append_candidate(candidates, "short", "overnight_high", bar.get("overnight_high"))
        if mode in {"value_area_pullback", "profile_aoi_pullback", "all_aoi_pullback"}:
            prefix = self.cached_profile_prefix
            self._append_candidate(candidates, "long", "prior_value_area_low", bar.get(f"{prefix}_val"))
            self._append_candidate(candidates, "short", "prior_value_area_high", bar.get(f"{prefix}_vah"))
        if mode in {"lvn_pullback", "profile_aoi_pullback", "all_aoi_pullback"}:
            prefix = self.cached_profile_prefix
            self._append_candidate(candidates, "long", "prior_lvn_near_low", bar.get(f"{prefix}_lvn_near_low"))
            self._append_candidate(candidates, "short", "prior_lvn_near_high", bar.get(f"{prefix}_lvn_near_high"))
        if mode in {"profile_aoi_pullback", "all_aoi_pullback"}:
            prefix = self.cached_profile_prefix
            self._append_candidate(candidates, "long", "prior_poc_reclaim", bar.get(f"{prefix}_poc"))
            self._append_candidate(candidates, "short", "prior_poc_reject", bar.get(f"{prefix}_poc"))
        return candidates

    def _append_candidate(
        self,
        candidates: list[tuple[str, str, float]],
        direction: str,
        aoi_type: str,
        raw_level,
    ) -> None:
        level = _finite_float(raw_level)
        if level is not None:
            candidates.append((direction, aoi_type, level))

    def _opening_range(self) -> dict | None:
        if len(self.current_session_bars) < self.opening_range_minutes:
            return None
        first = self.current_session_bars[0]
        session_start = pd.Timestamp(first["timestamp"])
        opening_end = session_start + pd.Timedelta(minutes=self.opening_range_minutes)
        opening_bars = [
            bar
            for bar in self.current_session_bars
            if pd.Timestamp(bar["timestamp"]) < opening_end
        ]
        if len(opening_bars) < self.opening_range_minutes:
            return None
        return {
            "high": max(float(bar["high"]) for bar in opening_bars),
            "low": min(float(bar["low"]) for bar in opening_bars),
            "start_timestamp": session_start,
            "end_timestamp": opening_end,
        }

    def _bar_values(self, bar: pd.Series) -> dict[str, float] | None:
        values = {
            "open": _finite_float(bar.get("open")),
            "high": _finite_float(bar.get("high")),
            "low": _finite_float(bar.get("low")),
            "close": _finite_float(bar.get("close")),
            "volume": _finite_float(bar.get("volume")),
            "signed_volume": _finite_float(bar.get("signed_volume")),
        }
        if any(value is None for value in values.values()) or values["volume"] <= 0:
            return None
        return values

    def _mes_metrics(self, bar: pd.Series) -> dict[str, float] | None:
        suffix = str(self.lookback_minutes)
        if self.share_mode == "trade":
            share_col = f"mes_trade_share_{suffix}"
            rank_col = f"mes_trade_share_{suffix}_rank{self.rank_window}"
        else:
            share_col = f"mes_participation_share_{suffix}"
            rank_col = f"mes_participation_share_{suffix}_rank{self.rank_window}"
        share = _finite_float(bar.get(share_col))
        rank = _finite_float(bar.get(rank_col))
        es_return = _finite_float(bar.get(f"es_return_ticks_{suffix}"))
        if None in {share, rank, es_return}:
            return None
        return {
            "share": share,
            "share_rank": rank,
            "es_return_ticks": es_return,
            "share_col": share_col,
            "rank_col": rank_col,
        }

    def _trend_return_ticks(self, session_date, signal_timestamp: pd.Timestamp) -> dict[str, object] | None:
        history = self.history_by_session.get(session_date) or {}
        trend_end_timestamp = signal_timestamp - pd.Timedelta(minutes=self.lookback_minutes)
        trend_start_timestamp = trend_end_timestamp - pd.Timedelta(minutes=self.trend_lookback_minutes)
        close_end = _finite_float(history.get(trend_end_timestamp))
        close_start = _finite_float(history.get(trend_start_timestamp))
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

    def _trend_and_pullback_match(self, direction: str, metrics: dict[str, float], trend: dict[str, object]) -> bool:
        trend_return = float(trend["trend_return_ticks"])
        if direction == "long":
            return (
                trend_return >= self.min_trend_return_ticks
                and metrics["es_return_ticks"] <= -self.min_abs_return_ticks
            )
        return (
            trend_return <= -self.min_trend_return_ticks
            and metrics["es_return_ticks"] >= self.min_abs_return_ticks
        )

    def _aoi_reclaim_confirms(self, direction: str, bar: pd.Series, values: dict[str, float], level: float) -> bool:
        probe = self.min_probe_ticks * self.tick_size
        confirm = self.confirmation_ticks * self.tick_size
        if not self._delta_confirms(direction, values):
            return False
        if self.require_footprint_absorption and not self._footprint_absorption_confirms(direction, bar):
            return False
        if direction == "long":
            return (
                values["low"] <= level - probe
                and values["close"] >= level + confirm
                and values["close"] > values["open"]
            )
        return (
            values["high"] >= level + probe
            and values["close"] <= level - confirm
            and values["close"] < values["open"]
        )

    def _delta_confirms(self, direction: str, values: dict[str, float]) -> bool:
        if self.min_delta_imbalance <= 0:
            return True
        imbalance = values["signed_volume"] / values["volume"]
        if direction == "long":
            return imbalance >= self.min_delta_imbalance
        return imbalance <= -self.min_delta_imbalance

    def _footprint_absorption_confirms(self, direction: str, bar: pd.Series) -> bool:
        if direction == "long":
            return _truthy(bar.get("footprint_absorption_long")) or _truthy(
                bar.get("footprint_sell_imbalance_below_close")
            )
        return _truthy(bar.get("footprint_absorption_short")) or _truthy(
            bar.get("footprint_buy_imbalance_above_close")
        )

    def _signal(
        self,
        direction: str,
        aoi_type: str,
        level: float,
        bar: pd.Series,
        values: dict[str, float],
        metrics: dict[str, float],
        trend: dict[str, object],
        signal_timestamp: pd.Timestamp,
    ) -> Signal:
        delta_imbalance = values["signed_volume"] / values["volume"]
        fields = {
            "setup_mode": self.setup_mode,
            "aoi_type": aoi_type,
            "aoi_level": level,
            "lookback_minutes": self.lookback_minutes,
            "trend_lookback_minutes": self.trend_lookback_minutes,
            "rank_window": self.rank_window,
            "share_mode": self.share_mode,
            "mes_share": metrics["share"],
            "mes_share_rank": metrics["share_rank"],
            "mes_share_column": metrics["share_col"],
            "mes_rank_column": metrics["rank_col"],
            "es_pullback_return_ticks": metrics["es_return_ticks"],
            "trend_return_ticks": trend["trend_return_ticks"],
            "trend_start_timestamp": trend["trend_start_timestamp"],
            "trend_end_timestamp": trend["trend_end_timestamp"],
            "min_share_rank": self.min_share_rank,
            "min_abs_return_ticks": self.min_abs_return_ticks,
            "min_trend_return_ticks": self.min_trend_return_ticks,
            "min_probe_ticks": self.min_probe_ticks,
            "confirmation_ticks": self.confirmation_ticks,
            "delta_imbalance": delta_imbalance,
            "min_delta_imbalance": self.min_delta_imbalance,
            "require_footprint_absorption": self.require_footprint_absorption,
            "signal_timestamp": signal_timestamp,
            "signal_close_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "source_quality_label": "MES participation/crowding proxy plus completed trend and AOI reclaim fields",
        }
        return Signal(
            direction=direction,
            level_type=f"{aoi_type}_{self.share_mode}_mes_trend_aoi_pullback",
            swept_level=level,
            sweep_timestamp=bar["timestamp"],
            sweep_high=values["high"],
            sweep_low=values["low"],
            reclaim_timestamp=signal_timestamp,
            metadata=fields.copy(),
            report_fields=fields,
        )

    def _validate(self) -> None:
        if self.setup_mode not in self._MODES:
            raise ValueError(f"entry.params.setup_mode must be one of {sorted(self._MODES)}.")
        if self.end_time <= self.start_time:
            raise ValueError("entry.params.end_time must be after start_time.")
        if self.bar_interval_minutes <= 0 or self.tick_size <= 0:
            raise ValueError("entry.params bar_interval_minutes and tick_size must be positive.")
        if (
            self.opening_range_minutes < 1
            or self.lookback_minutes < 1
            or self.trend_lookback_minutes < 1
            or self.rank_window < 1
        ):
            raise ValueError("entry.params windows must be positive.")
        if self.share_mode not in {"trade", "notional"}:
            raise ValueError("entry.params.share_mode must be trade or notional.")
        if not 0 <= self.min_share_rank <= 1:
            raise ValueError("entry.params.min_share_rank must be between zero and one.")
        if (
            self.min_abs_return_ticks < 0
            or self.min_trend_return_ticks < 0
            or self.min_probe_ticks < 0
            or self.confirmation_ticks < 0
        ):
            raise ValueError("entry.params return, trend, probe, and confirmation thresholds must be non-negative.")
        if self.min_delta_imbalance < 0:
            raise ValueError("entry.params.min_delta_imbalance must be non-negative.")
        if self.max_trades_per_day < 1:
            raise ValueError("entry.params.max_trades_per_day must be at least one.")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _truthy(value) -> bool:
    if value is None or pd.isna(value):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)
