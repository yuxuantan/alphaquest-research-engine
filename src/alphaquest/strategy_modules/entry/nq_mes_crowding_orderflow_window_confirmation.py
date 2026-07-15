from __future__ import annotations

from datetime import date
import math

import pandas as pd

from alphaquest.strategy_modules.entry.volatility_filtered_trend_mes_participation_crowding import (
    VolatilityFilteredTrendMesParticipationCrowdingEntry,
)


class NqMesCrowdingOrderflowWindowConfirmationEntry(
    VolatilityFilteredTrendMesParticipationCrowdingEntry
):
    name = "nq_mes_crowding_orderflow_window_confirmation"

    def __init__(self, params: dict):
        super().__init__(params)
        self.orderflow_window_minutes = int(params.get("orderflow_window_minutes", self.lookback_minutes))
        self.flow_mode = str(params.get("flow_mode", "signed_imbalance")).lower()
        self.confirmation_mode = str(params.get("confirmation_mode", "pressure_extension")).lower()
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.0))
        self.min_vwap_extension_ticks = float(params.get("min_vwap_extension_ticks", 4.0))
        self.min_reversal_bar_ticks = float(params.get("min_reversal_bar_ticks", 1.0))
        self.flow_state_by_day: dict[date, dict] = {}
        self._validate_orderflow()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0):
        if bool(bar.get("is_rth", False)):
            timestamp = pd.Timestamp(bar["timestamp"])
            bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
            self._append_flow_bar(self._flow_state(bar, timestamp), bar, bar_close)

        parent_state = None
        if bool(bar.get("is_rth", False)):
            parent_state = self._state(bar, pd.Timestamp(bar["timestamp"]))
        signal = super().on_bar_close(bar, trades_today=trades_today)
        if signal is None:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        flow_state = self._flow_state(bar, timestamp)
        observed = self._observed_values(flow_state, bar, bar_close, signal.direction)
        if not self._matches(observed):
            if parent_state is not None:
                parent_state["signaled"] = False
            return None

        report_fields = {
            "nq_orderflow_confirmation_mode": self.confirmation_mode,
            "nq_orderflow_flow_mode": self.flow_mode,
            "nq_orderflow_window_minutes": self.orderflow_window_minutes,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "min_vwap_extension_ticks": self.min_vwap_extension_ticks,
            "min_reversal_bar_ticks": self.min_reversal_bar_ticks,
            **observed,
        }
        signal.level_type = f"{signal.level_type}_nq_orderflow_window_confirmed"
        signal.metadata = {
            **signal.metadata,
            "nq_orderflow_confirmation_mode": self.confirmation_mode,
            "nq_orderflow_flow_mode": self.flow_mode,
            "nq_orderflow_imbalance": observed["primary_orderflow_imbalance"],
        }
        signal.report_fields = {**signal.report_fields, **report_fields}
        return signal

    def _flow_state(self, bar: pd.Series, timestamp: pd.Timestamp) -> dict:
        session_date = _date(bar.get("session_date", timestamp.date()))
        state = self.flow_state_by_day.get(session_date)
        if state is None:
            state = {"bars": []}
            self.flow_state_by_day[session_date] = state
        return state

    def _append_flow_bar(self, state: dict, bar: pd.Series, bar_close: pd.Timestamp) -> None:
        close = _finite_float(bar.get("close"))
        volume = max(_finite_float(bar.get("volume")) or 0.0, 0.0)
        state["bars"].append(
            {
                "bar_close": bar_close,
                "open": _finite_float(bar.get("open")),
                "close": close,
                "volume": volume,
                "pv": (close or 0.0) * volume,
                "signed_volume": _finite_float(bar.get("signed_volume")) or 0.0,
                "large10_volume": max(_finite_float(bar.get("large10_volume")) or 0.0, 0.0),
                "large10_signed_volume": _finite_float(bar.get("large10_signed_volume")) or 0.0,
                "large20_volume": max(_finite_float(bar.get("large20_volume")) or 0.0, 0.0),
                "large20_signed_volume": _finite_float(bar.get("large20_signed_volume")) or 0.0,
            }
        )
        cutoff = bar_close - pd.Timedelta(minutes=self.orderflow_window_minutes + 2)
        state["bars"] = [row for row in state["bars"] if row["bar_close"] >= cutoff]

    def _observed_values(
        self,
        state: dict,
        bar: pd.Series,
        bar_close: pd.Timestamp,
        direction: str,
    ) -> dict[str, float | str]:
        window_start = bar_close - pd.Timedelta(minutes=self.orderflow_window_minutes)
        rows = [
            row
            for row in state["bars"]
            if window_start < row["bar_close"] <= bar_close
        ]
        volume = sum(row["volume"] for row in rows)
        pv = sum(row["pv"] for row in rows)
        signed_volume = sum(row["signed_volume"] for row in rows)
        large10_volume = sum(row["large10_volume"] for row in rows)
        large10_signed_volume = sum(row["large10_signed_volume"] for row in rows)
        large20_volume = sum(row["large20_volume"] for row in rows)
        large20_signed_volume = sum(row["large20_signed_volume"] for row in rows)
        window_vwap = pv / volume if volume > 0 else math.nan
        close = _finite_float(bar.get("close"))
        open_ = _finite_float(bar.get("open"))
        price_vs_vwap_ticks = (
            (close - window_vwap) / self.tick_size
            if close is not None and math.isfinite(window_vwap)
            else math.nan
        )
        bar_return_ticks = (
            (close - open_) / self.tick_size
            if close is not None and open_ is not None
            else math.nan
        )
        primary, secondary = self._flow_values(
            volume,
            signed_volume,
            large10_volume,
            large10_signed_volume,
            large20_volume,
            large20_signed_volume,
        )
        pressure_mult = -1.0 if direction == "long" else 1.0
        signed_price_extension = pressure_mult * price_vs_vwap_ticks
        signed_bar_reversal = -pressure_mult * bar_return_ticks
        return {
            "nq_orderflow_window_start": window_start,
            "nq_orderflow_window_end": bar_close,
            "nq_orderflow_window_bar_count": len(rows),
            "nq_orderflow_window_volume": volume,
            "nq_orderflow_window_vwap": window_vwap,
            "nq_orderflow_price_vs_vwap_ticks": price_vs_vwap_ticks,
            "nq_orderflow_signed_price_extension_ticks": signed_price_extension,
            "nq_orderflow_bar_return_ticks": bar_return_ticks,
            "nq_orderflow_signed_bar_reversal_ticks": signed_bar_reversal,
            "primary_orderflow_imbalance": primary,
            "secondary_orderflow_imbalance": secondary,
            "signed_pressure_orderflow_imbalance": pressure_mult * primary if primary is not None else math.nan,
            "signed_secondary_pressure_orderflow_imbalance": (
                pressure_mult * secondary if secondary is not None else math.nan
            ),
        }

    def _flow_values(
        self,
        volume: float,
        signed_volume: float,
        large10_volume: float,
        large10_signed_volume: float,
        large20_volume: float,
        large20_signed_volume: float,
    ) -> tuple[float | None, float | None]:
        signed = _ratio(signed_volume, volume)
        large10 = _ratio(large10_signed_volume, large10_volume)
        large20 = _ratio(large20_signed_volume, large20_volume)
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

    def _matches(self, observed: dict[str, float | str]) -> bool:
        primary = observed["signed_pressure_orderflow_imbalance"]
        secondary = observed["signed_secondary_pressure_orderflow_imbalance"]
        flow_ok = (
            _finite(primary)
            and primary >= self.min_orderflow_imbalance
            and (not _finite(secondary) or secondary >= self.min_orderflow_imbalance)
        )
        if not flow_ok:
            return False
        if self.confirmation_mode == "pressure_extension":
            return True
        if self.confirmation_mode == "vwap_pressure":
            return (
                _finite(observed["nq_orderflow_signed_price_extension_ticks"])
                and observed["nq_orderflow_signed_price_extension_ticks"] >= self.min_vwap_extension_ticks
            )
        if self.confirmation_mode == "absorption_reversal_bar":
            return (
                _finite(observed["nq_orderflow_signed_bar_reversal_ticks"])
                and observed["nq_orderflow_signed_bar_reversal_ticks"] >= self.min_reversal_bar_ticks
            )
        raise ValueError(
            "confirmation_mode must be pressure_extension, vwap_pressure, "
            "or absorption_reversal_bar."
        )

    def _validate_orderflow(self) -> None:
        if self.orderflow_window_minutes <= 0:
            raise ValueError("entry.params.orderflow_window_minutes must be greater than 0.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("entry.params.min_orderflow_imbalance must be non-negative.")
        if self.confirmation_mode not in {
            "pressure_extension",
            "vwap_pressure",
            "absorption_reversal_bar",
        }:
            raise ValueError(
                "entry.params.confirmation_mode must be pressure_extension, "
                "vwap_pressure, or absorption_reversal_bar."
            )


def _date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    out = numerator / denominator
    return out if math.isfinite(out) else None
