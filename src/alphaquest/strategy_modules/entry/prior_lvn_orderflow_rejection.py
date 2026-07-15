from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class PriorLvnOrderflowRejectionEntry:
    name = "prior_lvn_orderflow_rejection"

    _FLOW_COLUMNS = {
        "signed_volume": ("signed_volume", "volume"),
        "signed": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "two_sided_lvn_rejection")).lower()
        self.start_time = parse_time(params.get("start_time", "09:35:00"))
        self.end_time = parse_time(params.get("end_time", "15:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_prior_profile_bars = int(params.get("min_prior_profile_bars", 50))
        self.lvn_quantile = float(params.get("lvn_quantile", 0.20))
        self.min_sweep_ticks = int(params.get("min_sweep_ticks", 2))
        self.reclaim_buffer_ticks = int(params.get("reclaim_buffer_ticks", 0))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.0))
        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.current_session = None
        self.current_session_bars: list[pd.Series] = []
        self.prior_profile: dict | None = None
        self.signaled_sessions: set = set()
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._roll_session(bar)
        if not bool(bar.get("is_rth", False)):
            return None
        self.current_session_bars.append(bar)

        session_date = bar.get("session_date")
        if self.prior_profile is None or session_date in self.signaled_sessions:
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if bar_close.time() < self.start_time or bar_close.time() > self.end_time:
            return None

        imbalance = self._orderflow_imbalance(bar)
        if imbalance is None:
            return None

        signal = self._signal_from_bar(bar, bar_close, imbalance)
        if signal is not None:
            self.signaled_sessions.add(session_date)
        return signal

    def _roll_session(self, bar: pd.Series) -> None:
        session_date = bar.get("session_date")
        if self.current_session is None:
            self.current_session = session_date
            return
        if session_date == self.current_session:
            return
        self.prior_profile = self._build_profile(self.current_session, self.current_session_bars)
        self.current_session = session_date
        self.current_session_bars = []

    def _signal_from_bar(self, bar: pd.Series, signal_timestamp: pd.Timestamp, imbalance: float) -> Signal | None:
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        open_price = _finite_float(bar.get("open"))
        close = _finite_float(bar.get("close"))
        if high is None or low is None or open_price is None or close is None:
            return None

        lvn_prices = self.prior_profile.get("lvn_prices", []) if self.prior_profile else []
        if not lvn_prices:
            return None
        sweep = self.min_sweep_ticks * self.tick_size
        buffer = self.reclaim_buffer_ticks * self.tick_size

        if self.setup_mode in {"two_sided_lvn_rejection", "downside_lvn_reclaim_long"} and self.allow_long:
            candidates = [
                price
                for price in lvn_prices
                if low <= price - sweep and close >= price + buffer and close > open_price
            ]
            if candidates and imbalance >= self.min_orderflow_imbalance:
                return self._signal(
                    "long",
                    max(candidates),
                    bar,
                    signal_timestamp,
                    imbalance,
                    "downside_lvn_reclaim",
                )

        if self.setup_mode in {"two_sided_lvn_rejection", "upside_lvn_reject_short"} and self.allow_short:
            candidates = [
                price
                for price in lvn_prices
                if high >= price + sweep and close <= price - buffer and close < open_price
            ]
            if candidates and imbalance <= -self.min_orderflow_imbalance:
                return self._signal(
                    "short",
                    min(candidates),
                    bar,
                    signal_timestamp,
                    imbalance,
                    "upside_lvn_reject",
                )
        return None

    def _signal(
        self,
        direction: str,
        level: float,
        bar: pd.Series,
        signal_timestamp: pd.Timestamp,
        imbalance: float,
        rejection_type: str,
    ) -> Signal:
        profile = self.prior_profile or {}
        high = float(bar["high"])
        low = float(bar["low"])
        return Signal(
            direction=direction,
            level_type=f"prior_lvn_{rejection_type}",
            swept_level=level,
            sweep_timestamp=bar["timestamp"],
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=signal_timestamp,
            breakout_level=level,
            metadata={
                "setup_mode": self.setup_mode,
                "prior_profile_session": profile.get("session_date"),
                "prior_lvn_price": level,
                "prior_lvn_quantile": self.lvn_quantile,
                "prior_profile_total_volume": profile.get("total_volume"),
                "prior_profile_bars": profile.get("bar_count"),
                "flow_mode": self.flow_mode,
                "orderflow_imbalance": imbalance,
                "min_orderflow_imbalance": self.min_orderflow_imbalance,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields={
                "setup_mode": self.setup_mode,
                "prior_profile_session": profile.get("session_date"),
                "prior_lvn_price": level,
                "prior_lvn_quantile": self.lvn_quantile,
                "prior_lvn_count": profile.get("lvn_count"),
                "prior_profile_total_volume": profile.get("total_volume"),
                "prior_profile_bars": profile.get("bar_count"),
                "rejection_type": rejection_type,
                "flow_mode": self.flow_mode,
                "orderflow_imbalance": imbalance,
                "min_orderflow_imbalance": self.min_orderflow_imbalance,
                "signal_timestamp": signal_timestamp,
                "intended_entry_timestamp": signal_timestamp,
                "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
        )

    def _orderflow_imbalance(self, bar: pd.Series) -> float | None:
        signed_col, volume_col = self._FLOW_COLUMNS[self.flow_mode]
        signed = _finite_float(bar.get(signed_col))
        volume = _finite_float(bar.get(volume_col))
        if signed is None or volume is None or volume <= 0:
            return None
        imbalance = signed / volume
        return imbalance if math.isfinite(imbalance) else None

    def _build_profile(self, session_date, bars: list[pd.Series]) -> dict | None:
        if len(bars) < self.min_prior_profile_bars:
            return None
        volume_by_tick: dict[int, float] = {}
        bar_count = 0
        for bar in bars:
            volume = _finite_float(bar.get("volume"))
            low = _finite_float(bar.get("low"))
            high = _finite_float(bar.get("high"))
            if volume is None or volume <= 0 or low is None or high is None:
                continue
            low_tick = math.floor(low / self.tick_size)
            high_tick = math.ceil(high / self.tick_size)
            if high_tick < low_tick:
                continue
            ticks = list(range(low_tick, high_tick + 1))
            if not ticks:
                continue
            per_tick = volume / len(ticks)
            for tick in ticks:
                volume_by_tick[tick] = volume_by_tick.get(tick, 0.0) + per_tick
            bar_count += 1
        if bar_count < self.min_prior_profile_bars or not volume_by_tick:
            return None
        prices = sorted(volume_by_tick)
        total_volume = sum(volume_by_tick.values())
        if total_volume <= 0:
            return None
        threshold = _quantile(list(volume_by_tick.values()), self.lvn_quantile)
        lvn_ticks = [tick for tick in prices if volume_by_tick[tick] <= threshold]
        return {
            "session_date": session_date,
            "lvn_prices": [tick * self.tick_size for tick in lvn_ticks],
            "lvn_count": len(lvn_ticks),
            "total_volume": total_volume,
            "bar_count": bar_count,
            "lvn_volume_threshold": threshold,
        }

    def _validate(self) -> None:
        if self.setup_mode not in {"two_sided_lvn_rejection", "downside_lvn_reclaim_long", "upside_lvn_reject_short"}:
            raise ValueError(
                "entry.params.setup_mode must be two_sided_lvn_rejection, "
                "downside_lvn_reclaim_long, or upside_lvn_reject_short."
            )
        if self.end_time <= self.start_time:
            raise ValueError("entry.params.end_time must be after start_time.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be greater than 0.")
        if self.min_prior_profile_bars <= 0:
            raise ValueError("entry.params.min_prior_profile_bars must be greater than 0.")
        if not 0 < self.lvn_quantile < 1:
            raise ValueError("entry.params.lvn_quantile must be in (0, 1).")
        if self.min_sweep_ticks < 0 or self.reclaim_buffer_ticks < 0:
            raise ValueError("entry.params sweep/reclaim ticks must be non-negative.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("entry.params.min_orderflow_imbalance must be non-negative.")
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError("entry.params.flow_mode must be signed_volume, signed, large10, or large20.")
        if self.max_trades_per_day < 1:
            raise ValueError("entry.params.max_trades_per_day must be at least 1.")


def _quantile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    index = int(math.floor((len(ordered) - 1) * fraction))
    return ordered[max(0, min(index, len(ordered) - 1))]


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
