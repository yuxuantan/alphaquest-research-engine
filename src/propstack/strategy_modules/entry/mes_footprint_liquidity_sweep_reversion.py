from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class MesFootprintLiquiditySweepReversionEntry:
    name = "mes_footprint_liquidity_sweep_reversion"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", self.name))
        self.start_time = parse_time(params.get("start_time", "10:00:00"))
        self.end_time = parse_time(params.get("end_time", "15:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.lookback_bars = int(params.get("lookback_bars", 60))
        self.min_sweep_ticks = float(params.get("min_sweep_ticks", 1.0))
        self.reclaim_buffer_ticks = float(params.get("reclaim_buffer_ticks", 0.0))
        self.participation_window = int(params.get("participation_window", 15))
        self.rank_window = int(params.get("rank_window", 252))
        self.share_mode = str(params.get("share_mode", "notional")).lower()
        self.share_rank_min = float(params.get("share_rank_min", 0.55))
        self.mes_imbalance_column = str(
            params.get("mes_imbalance_column", f"mes_trade_orderflow_imbalance_{self.participation_window}")
        )
        self.min_mes_imbalance = float(params.get("min_mes_imbalance", 0.05))
        self.min_absorption_volume = float(params.get("min_absorption_volume", 20.0))
        self.direction = str(params.get("direction", "both")).lower()
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = bar.get("session_date", timestamp.date())
        state = self.state_by_day.setdefault(session_date, {"bars": [], "signaled": False})
        signal = None
        if trades_today < self.max_trades_per_day and not state["signaled"]:
            signal = self._signal_from_completed_bar(bar, state["bars"])
            if signal is not None:
                state["signaled"] = True
        state["bars"].append(bar.copy())
        return signal

    def _signal_from_completed_bar(self, bar: pd.Series, prior_bars: list[pd.Series]) -> Signal | None:
        timestamp = pd.Timestamp(bar["timestamp"])
        if timestamp.time() < self.start_time or timestamp.time() > self.end_time:
            return None
        if len(prior_bars) < self.lookback_bars:
            return None

        window = prior_bars[-self.lookback_bars :]
        rolling_high = max(float(item["high"]) for item in window)
        rolling_low = min(float(item["low"]) for item in window)
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        close = _finite_float(bar.get("close"))
        if None in {high, low, close}:
            return None

        share_rank = self._share_rank(bar)
        mes_imbalance = _finite_float(bar.get(self.mes_imbalance_column))
        if share_rank is None or mes_imbalance is None or share_rank < self.share_rank_min:
            return None

        sweep = self.min_sweep_ticks * self.tick_size
        reclaim = self.reclaim_buffer_ticks * self.tick_size
        if (
            self.direction in {"long", "both"}
            and low <= rolling_low - sweep
            and close >= rolling_low + reclaim
            and mes_imbalance <= -self.min_mes_imbalance
            and self._footprint_absorption_passes(bar, "long", close)
        ):
            return self._signal("long", bar, rolling_low, rolling_high, share_rank, mes_imbalance)
        if (
            self.direction in {"short", "both"}
            and high >= rolling_high + sweep
            and close <= rolling_high - reclaim
            and mes_imbalance >= self.min_mes_imbalance
            and self._footprint_absorption_passes(bar, "short", close)
        ):
            return self._signal("short", bar, rolling_low, rolling_high, share_rank, mes_imbalance)
        return None

    def _share_rank(self, bar: pd.Series) -> float | None:
        prefix = "mes_trade_share" if self.share_mode == "trade" else "mes_participation_share"
        return _finite_float(bar.get(f"{prefix}_{self.participation_window}_rank{self.rank_window}"))

    def _footprint_absorption_passes(self, bar: pd.Series, direction: str, close: float) -> bool:
        if direction == "long":
            absorption = _finite_float(bar.get("footprint_absorption_long")) or 0.0
            volume = _finite_float(bar.get("footprint_max_sell_imbalance_volume")) or 0.0
            price = _finite_float(bar.get("footprint_highest_sell_imbalance_price"))
            return absorption > 0 and volume >= self.min_absorption_volume and price is not None and price < close
        absorption = _finite_float(bar.get("footprint_absorption_short")) or 0.0
        volume = _finite_float(bar.get("footprint_max_buy_imbalance_volume")) or 0.0
        price = _finite_float(bar.get("footprint_lowest_buy_imbalance_price"))
        return absorption > 0 and volume >= self.min_absorption_volume and price is not None and price > close

    def _signal(
        self,
        direction: str,
        bar: pd.Series,
        rolling_low: float,
        rolling_high: float,
        share_rank: float,
        mes_imbalance: float,
    ) -> Signal:
        level = rolling_low if direction == "long" else rolling_high
        volume_col = (
            "footprint_max_sell_imbalance_volume"
            if direction == "long"
            else "footprint_max_buy_imbalance_volume"
        )
        price_col = (
            "footprint_highest_sell_imbalance_price"
            if direction == "long"
            else "footprint_lowest_buy_imbalance_price"
        )
        report_fields = {
            "setup_mode": self.setup_mode,
            "feature_method": "rolling_range_sweep_with_footprint_absorption_and_mes_crowding",
            "rolling_low": rolling_low,
            "rolling_high": rolling_high,
            "lookback_bars": self.lookback_bars,
            "min_sweep_ticks": self.min_sweep_ticks,
            "reclaim_buffer_ticks": self.reclaim_buffer_ticks,
            "share_mode": self.share_mode,
            "participation_window": self.participation_window,
            "rank_window": self.rank_window,
            "share_rank": share_rank,
            "share_rank_min": self.share_rank_min,
            "mes_imbalance_column": self.mes_imbalance_column,
            "mes_imbalance": mes_imbalance,
            "min_mes_imbalance": self.min_mes_imbalance,
            "footprint_absorption_volume": _finite_float(bar.get(volume_col)) or 0.0,
            "footprint_absorption_price": _finite_float(bar.get(price_col)) or 0.0,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=f"mes_footprint_liquidity_sweep_{self.setup_mode}",
            swept_level=float(level),
            sweep_timestamp=bar["timestamp"],
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=bar["timestamp"],
            metadata=report_fields.copy(),
            report_fields=report_fields,
        )

    def _validate(self) -> None:
        if self.lookback_bars < 2:
            raise ValueError("entry.params.lookback_bars must be at least 2.")
        if self.min_sweep_ticks < 0 or self.reclaim_buffer_ticks < 0:
            raise ValueError("entry sweep/reclaim ticks must be non-negative.")
        if self.participation_window <= 0 or self.rank_window <= 0:
            raise ValueError("entry participation_window and rank_window must be positive.")
        if self.share_mode not in {"notional", "trade"}:
            raise ValueError("entry.params.share_mode must be notional or trade.")
        if not 0 <= self.share_rank_min <= 1:
            raise ValueError("entry.params.share_rank_min must be between 0 and 1.")
        if self.min_mes_imbalance < 0:
            raise ValueError("entry.params.min_mes_imbalance must be non-negative.")
        if self.min_absorption_volume <= 0:
            raise ValueError("entry.params.min_absorption_volume must be positive.")
        if self.direction not in {"long", "short", "both"}:
            raise ValueError("entry.params.direction must be long, short, or both.")
        if self.max_trades_per_day <= 0:
            raise ValueError("entry.params.max_trades_per_day must be positive.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be positive.")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
