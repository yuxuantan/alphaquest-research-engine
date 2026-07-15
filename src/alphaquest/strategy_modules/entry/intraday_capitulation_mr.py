from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class IntradayCapitulationMREntry:
    name = "intraday_capitulation_mr"

    def __init__(self, params: dict):
        self.params = params
        self.state_by_day: dict = {}

    def _state(self, session_date):
        return self.state_by_day.setdefault(
            session_date,
            {
                "current_bar": None,
                "indicator_bars": [],
                "signaled": False,
            },
        )

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= int(self.params.get("max_trades_per_day", 1)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        rth_start = parse_time(self.params.get("rth_start", "09:30:00"))
        rth_end = parse_time(self.params.get("rth_end", "16:15:00"))
        if timestamp.time() < rth_start or timestamp.time() >= rth_end:
            return None

        session_date = bar["session_date"]
        state = self._state(session_date)
        if state["signaled"]:
            return None

        window_start = self._window_start(timestamp, rth_start)
        if window_start is None:
            return None

        current = state["current_bar"]
        if current is None or current["start_timestamp"] != window_start:
            state["current_bar"] = self._new_aggregate_bar(bar, window_start)
        else:
            self._update_aggregate_bar(current, bar)

        current = state["current_bar"]
        if not self._bar_complete(timestamp, window_start):
            return None

        signal = self._signal_from_completed_bar(current, session_date, state["indicator_bars"])
        state["indicator_bars"].append(current.copy())
        state["current_bar"] = None
        if signal is not None:
            state["signaled"] = True
        return signal

    def _signal_from_completed_bar(
        self,
        completed_bar: dict,
        session_date,
        indicator_bars: list[dict],
    ) -> Signal | None:
        if self.params.get("allow_long", True) is False:
            return None
        if bool(self.params.get("require_full_window", True)):
            expected = self._bar_count()
            if completed_bar["bar_count"] < expected:
                return None

        last_signal_time = parse_time(self.params.get("last_signal_time", "16:00:00"))
        if completed_bar["end_timestamp"].time() > last_signal_time:
            return None

        open_price = float(completed_bar["open"])
        high = float(completed_bar["high"])
        low = float(completed_bar["low"])
        close = float(completed_bar["close"])
        volume = float(completed_bar["volume"])
        vwap = completed_bar.get("vwap")
        if not all(math.isfinite(value) for value in [open_price, high, low, close, volume]):
            return None
        if vwap is None or pd.isna(vwap) or not math.isfinite(float(vwap)):
            return None
        tick_size = float(self.params.get("tick_size", 0.25))
        if tick_size <= 0:
            raise ValueError("entry.params.tick_size must be greater than 0.")
        down_move_ticks = (open_price - close) / tick_size
        if down_move_ticks < float(self.params.get("min_down_move_ticks", 0.0)):
            return None

        bar_range = high - low
        if bar_range <= 0:
            return None
        close_location_from_low = (close - low) / bar_range
        if close >= open_price:
            return None
        if close_location_from_low > float(self.params.get("max_close_location_from_low", 0.25)):
            return None

        signed_volume = completed_bar.get("signed_volume")
        signed_imbalance = None
        if signed_volume is not None and not pd.isna(signed_volume) and volume > 0:
            signed_imbalance = float(signed_volume) / volume
        min_sell_imbalance = float(self.params.get("min_sell_imbalance", 0.0))
        if min_sell_imbalance > 0:
            if signed_imbalance is None or signed_imbalance > -min_sell_imbalance:
                return None

        rsi = self._rsi([*indicator_bars, completed_bar], int(self.params.get("rsi_period", 14)))
        if rsi is None or rsi >= float(self.params.get("max_rsi", 35.0)):
            return None

        if close > float(vwap):
            return None

        volume_window = int(self.params.get("volume_avg_window", 20))
        min_volume_avg_bars = int(self.params.get("min_volume_avg_bars", volume_window))
        prior_volumes = [float(item["volume"]) for item in indicator_bars[-volume_window:]]
        if len(prior_volumes) < min_volume_avg_bars:
            return None
        avg_volume = sum(prior_volumes) / len(prior_volumes)
        if avg_volume <= 0:
            return None
        volume_ratio = volume / avg_volume
        if volume_ratio <= float(self.params.get("min_volume_ratio", 1.5)):
            return None

        return Signal(
            direction="long",
            level_type="intraday_capitulation_mr",
            swept_level=low,
            sweep_timestamp=completed_bar["start_timestamp"],
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=completed_bar["end_timestamp"],
            metadata={
                "capitulation_close": close,
                "capitulation_vwap": float(vwap),
                "capitulation_rsi": rsi,
                "capitulation_volume_ratio": volume_ratio,
                "capitulation_close_location_from_low": close_location_from_low,
                "capitulation_down_move_ticks": down_move_ticks,
                "capitulation_signed_imbalance": signed_imbalance,
            },
            report_fields={
                "capitulation_bar_start_timestamp": completed_bar["start_timestamp"],
                "capitulation_bar_end_timestamp": completed_bar["end_timestamp"],
                "capitulation_timeframe_minutes": self._timeframe_minutes(),
                "capitulation_open": open_price,
                "capitulation_high": high,
                "capitulation_low": low,
                "capitulation_close": close,
                "capitulation_vwap": float(vwap),
                "capitulation_volume": volume,
                "capitulation_avg_volume": avg_volume,
                "capitulation_volume_ratio": volume_ratio,
                "capitulation_rsi": rsi,
                "capitulation_close_location_from_low": close_location_from_low,
                "capitulation_down_move_ticks": down_move_ticks,
                "capitulation_signed_volume": signed_volume,
                "capitulation_signed_imbalance": signed_imbalance,
                "min_down_move_ticks": float(self.params.get("min_down_move_ticks", 0.0)),
                "min_sell_imbalance": min_sell_imbalance,
                "rsi_scope": "session",
                "volume_average_scope": "session",
                "session_date": session_date,
            },
        )

    def _new_aggregate_bar(self, bar: pd.Series, window_start: pd.Timestamp) -> dict:
        return {
            "start_timestamp": window_start,
            "end_timestamp": window_start + pd.Timedelta(minutes=self._timeframe_minutes()),
            "open": float(bar["open"]),
            "high": float(bar["high"]),
            "low": float(bar["low"]),
            "close": float(bar["close"]),
            "volume": float(bar["volume"]),
            "signed_volume": self._bar_signed_volume(bar),
            "vwap": self._last_vwap(bar),
            "bar_count": 1,
        }

    def _update_aggregate_bar(self, aggregate: dict, bar: pd.Series) -> None:
        aggregate["high"] = max(float(aggregate["high"]), float(bar["high"]))
        aggregate["low"] = min(float(aggregate["low"]), float(bar["low"]))
        aggregate["close"] = float(bar["close"])
        aggregate["volume"] = float(aggregate["volume"]) + float(bar["volume"])
        aggregate["signed_volume"] = float(aggregate.get("signed_volume") or 0.0) + self._bar_signed_volume(bar)
        aggregate["vwap"] = self._last_vwap(bar)
        aggregate["bar_count"] += 1

    def _window_start(self, timestamp: pd.Timestamp, rth_start) -> pd.Timestamp | None:
        start = timestamp.replace(
            hour=rth_start.hour,
            minute=rth_start.minute,
            second=rth_start.second,
            microsecond=0,
        )
        elapsed_minutes = (timestamp - start).total_seconds() / 60.0
        if elapsed_minutes < 0:
            return None
        bucket = int(elapsed_minutes // self._timeframe_minutes())
        return start + pd.Timedelta(minutes=bucket * self._timeframe_minutes())

    def _bar_complete(self, timestamp: pd.Timestamp, window_start: pd.Timestamp) -> bool:
        close_timestamp = timestamp + pd.Timedelta(minutes=float(self.params.get("bar_interval_minutes", 1)))
        return close_timestamp >= window_start + pd.Timedelta(minutes=self._timeframe_minutes())

    def _bar_count(self) -> int:
        interval = float(self.params.get("bar_interval_minutes", 1))
        if interval <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than 0.")
        return max(1, int(math.ceil(self._timeframe_minutes() / interval)))

    def _timeframe_minutes(self) -> float:
        value = float(self.params.get("timeframe_minutes", 15))
        if value <= 0:
            raise ValueError("entry.params.timeframe_minutes must be greater than 0.")
        return value

    def _last_vwap(self, bar: pd.Series) -> float | None:
        if "vwap" not in bar or pd.isna(bar["vwap"]):
            return None
        return float(bar["vwap"])

    def _bar_signed_volume(self, bar: pd.Series) -> float:
        if "signed_volume" not in bar or pd.isna(bar["signed_volume"]):
            return 0.0
        return float(bar["signed_volume"])

    def _rsi(self, bars: list[dict], period: int) -> float | None:
        if period <= 0:
            raise ValueError("entry.params.rsi_period must be greater than 0.")
        closes = [float(item["close"]) for item in bars]
        if len(closes) <= period:
            return None

        changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [max(change, 0.0) for change in changes]
        losses = [max(-change, 0.0) for change in changes]
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        for gain, loss in zip(gains[period:], losses[period:]):
            avg_gain = ((avg_gain * (period - 1)) + gain) / period
            avg_loss = ((avg_loss * (period - 1)) + loss) / period

        if avg_loss == 0 and avg_gain == 0:
            return 50.0
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))
