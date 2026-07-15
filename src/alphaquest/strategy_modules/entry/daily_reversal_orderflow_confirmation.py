from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class DailyReversalOrderflowConfirmationEntry:
    name = "daily_reversal_orderflow_confirmation"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "daily_reversal_flow_confirm")).lower()
        self.direction_mode = str(params.get("direction_mode", "two_sided")).lower()
        self.rth_end = parse_time(params.get("rth_end", "16:00:00"))
        self.signal_time = parse_time(params.get("signal_time", "10:30:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.lookback_sessions = int(params.get("lookback_sessions", 1))
        self.min_abs_reversal_return_pct = float(params.get("min_abs_reversal_return_pct", 0.0))
        self.flow_window_bars = int(params.get("flow_window_bars", 12))
        self.min_reversal_flow_imbalance = float(params.get("min_reversal_flow_imbalance", 0.0))
        self.min_flow_volume = float(params.get("min_flow_volume", 0.0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.history: list[dict] = []
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        state = self._state(bar["session_date"])

        signal = None
        if not state["signaled"] and trades_today < self.max_trades_per_day and bar_close.time() == self.signal_time:
            signal = self._signal(bar, bar_close)
            if signal is not None:
                state["signaled"] = True

        if not state["recorded_close"] and bar_close.time() >= self.rth_end:
            self.history.append(
                {
                    "session_date": bar["session_date"],
                    "timestamp": bar_close,
                    "close": float(bar["close"]),
                }
            )
            state["recorded_close"] = True
        return signal

    def _state(self, session_date):
        return self.state_by_day.setdefault(session_date, {"signaled": False, "recorded_close": False})

    def _signal(self, bar: pd.Series, signal_timestamp: pd.Timestamp) -> Signal | None:
        if len(self.history) < self.lookback_sessions + 1:
            return None

        recent = self.history[-1]
        anchor = self.history[-(self.lookback_sessions + 1)]
        recent_close = float(recent["close"])
        anchor_close = float(anchor["close"])
        if anchor_close <= 0:
            return None

        reversal_return_pct = recent_close / anchor_close - 1.0
        if abs(reversal_return_pct) < self.min_abs_reversal_return_pct:
            return None

        direction = self._direction_from_return(reversal_return_pct)
        if direction is None:
            return None

        suffix = str(self.flow_window_bars)
        flow_imbalance = _finite_float(bar.get(f"trade_orderflow_imbalance_{suffix}"))
        flow_volume = _finite_float(bar.get(f"trade_orderflow_volume_{suffix}"))
        flow_signed_volume = _finite_float(bar.get(f"trade_orderflow_signed_volume_{suffix}"))
        flow_return_ticks = _finite_float(bar.get(f"trade_orderflow_return_ticks_{suffix}"))
        if flow_imbalance is None or flow_volume is None:
            return None
        if flow_volume < self.min_flow_volume:
            return None
        if direction == "long" and flow_imbalance < self.min_reversal_flow_imbalance:
            return None
        if direction == "short" and flow_imbalance > -self.min_reversal_flow_imbalance:
            return None

        report_fields = {
            "academic_source_key": "lehmann_1990_nagel_2012_cont_2014_reversal_flow_confirm",
            "setup_mode": self.setup_mode,
            "direction_mode": self.direction_mode,
            "signal_timestamp": signal_timestamp,
            "reversal_anchor_session_date": anchor["session_date"],
            "reversal_anchor_close": anchor_close,
            "reversal_recent_session_date": recent["session_date"],
            "reversal_recent_close": recent_close,
            "reversal_return_pct": reversal_return_pct,
            "lookback_sessions": self.lookback_sessions,
            "min_abs_reversal_return_pct": self.min_abs_reversal_return_pct,
            "flow_window_bars": self.flow_window_bars,
            "flow_window_minutes": self.flow_window_bars * self.bar_interval_minutes,
            "flow_return_ticks": flow_return_ticks,
            "flow_signed_volume": flow_signed_volume,
            "flow_volume": flow_volume,
            "flow_imbalance": flow_imbalance,
            "min_reversal_flow_imbalance": self.min_reversal_flow_imbalance,
            "min_flow_volume": self.min_flow_volume,
        }
        return Signal(
            direction=direction,
            level_type=f"daily_reversal_orderflow_confirmation_{self.setup_mode}",
            swept_level=recent_close,
            sweep_timestamp=recent["timestamp"],
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "confirmation_high": float(bar["high"]),
                "confirmation_low": float(bar["low"]),
                "confirmation_close": float(bar["close"]),
                "reversal_return_pct": reversal_return_pct,
                "flow_imbalance": flow_imbalance,
                "setup_mode": self.setup_mode,
                "direction_mode": self.direction_mode,
            },
            report_fields=report_fields,
        )

    def _direction_from_return(self, reversal_return_pct: float) -> str | None:
        if reversal_return_pct > 0:
            contrarian = "short"
        elif reversal_return_pct < 0:
            contrarian = "long"
        else:
            return None

        if self.direction_mode == "two_sided":
            return contrarian
        if self.direction_mode == "loss_long":
            return "long" if contrarian == "long" else None
        if self.direction_mode == "gain_short":
            return "short" if contrarian == "short" else None
        raise ValueError("direction_mode must be one of two_sided, loss_long, gain_short.")

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.lookback_sessions < 1:
            raise ValueError("lookback_sessions must be at least 1.")
        if self.flow_window_bars < 1:
            raise ValueError("flow_window_bars must be at least 1.")
        if self.min_abs_reversal_return_pct < 0:
            raise ValueError("min_abs_reversal_return_pct must be non-negative.")
        if self.min_reversal_flow_imbalance < 0:
            raise ValueError("min_reversal_flow_imbalance must be non-negative.")
        if self.min_flow_volume < 0:
            raise ValueError("min_flow_volume must be non-negative.")
        if self.max_trades_per_day < 1:
            raise ValueError("max_trades_per_day must be at least 1.")
        if self.direction_mode not in {"two_sided", "loss_long", "gain_short"}:
            raise ValueError("direction_mode must be one of two_sided, loss_long, gain_short.")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    out = float(value)
    return out if pd.notna(out) else None
