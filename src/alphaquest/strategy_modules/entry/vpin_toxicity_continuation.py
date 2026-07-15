from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class VpinToxicityContinuationEntry:
    name = "vpin_toxicity_continuation"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "prior_vpin_session_return_continuation")).lower()
        self.entry_time = parse_time(params.get("entry_time", "13:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:31:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.vpin_rank_cutoff = float(params.get("vpin_rank_cutoff", 0.45))
        self.drawdown_rank_cutoff = float(params.get("drawdown_rank_cutoff", 0.30))
        self.min_session_return = float(params.get("min_session_return", 0.0005))
        self.stop_pct = float(params.get("stop_pct", 0.02))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.0))
        self.vpin_rank_column = str(params.get("vpin_rank_column", "vpin_prior_rank21_at_1330"))
        self.drawdown_rank_column = str(
            params.get("drawdown_rank_column", "vpin_prior_drawdown_rank63_at_1330")
        )
        self.session_return_column = str(params.get("session_return_column", "vpin_session_ret"))
        self.vpin_proxy_column = str(params.get("vpin_proxy_column", "vpin_proxy_b010_l5"))
        self.max_session_return = _optional_float(params.get("max_session_return"))
        self.state_by_day: dict = {}

    def _state(self, session_date):
        return self.state_by_day.setdefault(
            session_date,
            {
                "signaled": False,
                "first_close": None,
                "high": None,
                "low": None,
                "bar_count": 0,
            },
        )

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None
        if self.bar_interval_minutes <= 0 or self.tick_size <= 0:
            raise ValueError("tick_size and bar_interval_minutes must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if not self.allow_long:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        state = self._state(bar["session_date"])
        self._update_state(state, bar)
        if state["signaled"]:
            return None

        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        signal_timestamp = self._session_timestamp(timestamp, self.entry_time)
        if bar_close != signal_timestamp:
            return None

        vpin_rank = _finite_float(bar.get(self.vpin_rank_column))
        drawdown_rank = _finite_float(bar.get(self.drawdown_rank_column))
        session_return = _finite_float(bar.get(self.session_return_column))
        if vpin_rank is None or drawdown_rank is None or session_return is None:
            return None
        if vpin_rank < self.vpin_rank_cutoff:
            return None
        if drawdown_rank < self.drawdown_rank_cutoff:
            return None
        if session_return < self.min_session_return:
            return None
        if self.max_session_return is not None and session_return > self.max_session_return:
            return None

        current_close = float(bar["close"])
        high = float(state["high"] if state["high"] is not None else bar["high"])
        low = float(state["low"] if state["low"] is not None else bar["low"])
        report_fields = {
            "academic_source_key": "easley_lopez_de_prado_ohara_2012_flow_toxicity",
            "academic_source_doi": "10.1093/rfs/hhs053",
            "setup_mode": self.setup_mode,
            "feature_method": "ohlcv_signed_volume_vpin_proxy",
            "vpin_rank_column": self.vpin_rank_column,
            "vpin_prior_rank": vpin_rank,
            "vpin_proxy_value": _finite_float(bar.get(self.vpin_proxy_column)),
            "drawdown_rank_column": self.drawdown_rank_column,
            "prior_session_drawdown_rank": drawdown_rank,
            "session_return_column": self.session_return_column,
            "session_return_at_signal": session_return,
            "min_session_return": self.min_session_return,
            "vpin_rank_cutoff": self.vpin_rank_cutoff,
            "drawdown_rank_cutoff": self.drawdown_rank_cutoff,
            "vpin_signal_timestamp": signal_timestamp,
            "vpin_intended_entry_timestamp": signal_timestamp,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "swept_level": current_close,
            "sweep_timestamp": timestamp,
            "sweep_high": high,
            "sweep_low": low,
            "reclaim_timestamp": signal_timestamp,
        }
        state["signaled"] = True
        return Signal(
            direction="long",
            level_type=f"vpin_toxicity_continuation_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=signal_timestamp,
            metadata={
                "confirmation_high": float(bar["high"]),
                "confirmation_low": float(bar["low"]),
                "confirmation_close": current_close,
                "setup_mode": self.setup_mode,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
                "vpin_prior_rank": vpin_rank,
                "prior_session_drawdown_rank": drawdown_rank,
                "session_return_at_signal": session_return,
            },
            report_fields=report_fields,
        )

    def _update_state(self, state: dict, bar: pd.Series) -> None:
        close = _finite_float(bar.get("close"))
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        if close is not None and state["first_close"] is None:
            state["first_close"] = close
        if high is not None:
            state["high"] = high if state["high"] is None else max(float(state["high"]), high)
        if low is not None:
            state["low"] = low if state["low"] is None else min(float(state["low"]), low)
        state["bar_count"] += 1

    def _session_timestamp(self, timestamp: pd.Timestamp, session_time) -> pd.Timestamp:
        return timestamp.replace(
            hour=session_time.hour,
            minute=session_time.minute,
            second=session_time.second,
            microsecond=0,
        )


def _optional_float(value) -> float | None:
    if value is None:
        return None
    return _finite_float(value)


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
