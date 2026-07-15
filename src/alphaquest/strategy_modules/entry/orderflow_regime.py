from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


_OPENING_DRIVE_MODES = {
    "opening_drive_flow_continuation",
    "opening_absorption_fade",
    "opening_price_flow_divergence_fade",
}


class OrderflowRegimeEntry:
    name = "orderflow_regime"

    def __init__(self, params: dict):
        self.params = params
        self.mode = str(params.get("mode", "flow_impulse_continuation")).lower()
        self.setup_mode = str(params.get("setup_mode", self.mode))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.pressure_rank_threshold = float(params.get("pressure_rank_threshold", 0.85))
        self.toxicity_rank_threshold = float(params.get("toxicity_rank_threshold", 0.75))
        self.min_return_ticks = float(params.get("min_return_ticks", 0.0))
        self.max_abs_return_ticks = float(params.get("max_abs_return_ticks", 2.0))
        self.min_open_return_ticks = float(params.get("min_open_return_ticks", 8.0))
        self.max_open_return_ticks = float(params.get("max_open_return_ticks", 8.0))
        self.min_open_imbalance = float(params.get("min_open_imbalance", 0.05))
        self.max_abs_open_imbalance = float(params.get("max_abs_open_imbalance", 0.02))
        self.min_open_volume_rank = float(params.get("min_open_volume_rank", 0.50))
        self.min_current_retrace_frac = float(params.get("min_current_retrace_frac", 0.20))
        self.max_current_retrace_frac = float(params.get("max_current_retrace_frac", 2.50))
        self.min_session_delta_ratio = float(params.get("min_session_delta_ratio", 0.0))
        self.min_vwap_extension_ticks = float(params.get("min_vwap_extension_ticks", 0.0))
        self.stop_pct = float(params.get("stop_pct", 0.005))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.5))
        self.slots = [_slot_config(params, slot, index) for index, slot in enumerate(params.get("slots") or [{}], start=1)]
        self.slots.sort(key=lambda item: item["entry_time"])
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        for slot in self.slots:
            signal_timestamp = _session_timestamp(timestamp, slot["entry_time"])
            if bar_close != signal_timestamp:
                continue
            signal = self._signal_for_slot(bar, timestamp, signal_timestamp, slot)
            if signal is not None:
                return signal
        return None

    def _signal_for_slot(
        self,
        bar: pd.Series,
        timestamp: pd.Timestamp,
        signal_timestamp: pd.Timestamp,
        slot: dict,
    ) -> Signal | None:
        if self.mode in _OPENING_DRIVE_MODES:
            return self._opening_signal_for_slot(bar, timestamp, signal_timestamp, slot)

        pressure_rank = _finite_float(bar.get(slot["pressure_rank_column"]))
        return_ticks = _finite_float(bar.get(slot["return_column"]))
        if pressure_rank is None or return_ticks is None:
            return None
        flow_sign = _flow_sign_from_rank(pressure_rank, self.pressure_rank_threshold)
        if flow_sign == 0:
            return None

        toxicity_rank = None
        if self.mode in {"toxicity_regime_continuation", "toxicity_regime_reversal"}:
            toxicity_rank = _finite_float(bar.get(slot["toxicity_rank_column"]))
            if toxicity_rank is None or toxicity_rank < self.toxicity_rank_threshold:
                return None
            if not _return_confirms(return_ticks, flow_sign, float(slot.get("min_return_ticks", self.min_return_ticks))):
                return None
            direction = _direction_from_flow(flow_sign, fade=self.mode.endswith("_reversal"))
        elif self.mode in {"flow_impulse_continuation", "flow_impulse_reversal"}:
            if not _return_confirms(return_ticks, flow_sign, self.min_return_ticks):
                return None
            direction = _direction_from_flow(flow_sign, fade=self.mode.endswith("_reversal"))
        elif self.mode == "absorption_exhaustion_reversal":
            effort_rank = _finite_float(bar.get(slot["effort_rank_column"])) if slot.get("effort_rank_column") else None
            if slot.get("effort_rank_column") and (
                effort_rank is None or effort_rank < float(slot["effort_rank_threshold"])
            ):
                return None
            if abs(return_ticks) > self.max_abs_return_ticks:
                return None
            direction = "short" if flow_sign > 0 else "long"
        elif self.mode == "prior_inventory_reversion":
            direction = _direction_from_flow(flow_sign, fade=True)
        else:
            raise ValueError(
                "orderflow_regime mode must be one of: "
                "flow_impulse_continuation, flow_impulse_reversal, absorption_exhaustion_reversal, "
                "toxicity_regime_continuation, toxicity_regime_reversal, prior_inventory_reversion, "
                "opening_drive_flow_continuation, opening_absorption_fade, "
                "opening_price_flow_divergence_fade."
            )

        current_close = float(bar["close"])
        flow_value = _finite_float(bar.get(slot["pressure_value_column"]))
        toxicity_value = _finite_float(bar.get(slot["toxicity_value_column"]))
        effort_rank = _finite_float(bar.get(slot["effort_rank_column"])) if slot.get("effort_rank_column") else None
        report_fields = {
            "academic_source_key": "cont_kukanov_stoikov_ofi_and_easley_lopez_de_prado_ohara_vpin",
            "setup_mode": slot["setup_mode"],
            "slot_id": slot["slot_id"],
            "feature_method": "sierra_bar_orderflow_regime",
            "orderflow_regime_mode": self.mode,
            "pressure_rank_column": slot["pressure_rank_column"],
            "pressure_rank": pressure_rank,
            "pressure_rank_threshold": self.pressure_rank_threshold,
            "flow_sign": flow_sign,
            "pressure_value_column": slot["pressure_value_column"],
            "pressure_value": flow_value,
            "return_column": slot["return_column"],
            "return_ticks": return_ticks,
            "min_return_ticks": self.min_return_ticks,
            "max_abs_return_ticks": self.max_abs_return_ticks,
            "toxicity_rank_column": slot.get("toxicity_rank_column"),
            "toxicity_rank": toxicity_rank,
            "toxicity_rank_threshold": self.toxicity_rank_threshold,
            "toxicity_value_column": slot.get("toxicity_value_column"),
            "toxicity_value": toxicity_value,
            "effort_rank_column": slot.get("effort_rank_column"),
            "effort_rank": effort_rank,
            "effort_rank_threshold": slot.get("effort_rank_threshold"),
            "orderflow_signal_timestamp": signal_timestamp,
            "orderflow_intended_entry_timestamp": signal_timestamp,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": slot["flatten_time"].strftime("%H:%M:%S"),
            "swept_level": current_close,
            "sweep_timestamp": timestamp,
            "sweep_high": float(bar["high"]),
            "sweep_low": float(bar["low"]),
            "reclaim_timestamp": signal_timestamp,
        }
        return Signal(
            direction=direction,
            level_type=f"orderflow_regime_{slot['setup_mode']}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": slot["setup_mode"],
                "slot_id": slot["slot_id"],
                "mode": self.mode,
                "pressure_rank": pressure_rank,
                "flow_sign": flow_sign,
                "return_ticks": return_ticks,
                "toxicity_rank": toxicity_rank,
                "effort_rank": effort_rank,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": slot["flatten_time"].strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _opening_signal_for_slot(
        self,
        bar: pd.Series,
        timestamp: pd.Timestamp,
        signal_timestamp: pd.Timestamp,
        slot: dict,
    ) -> Signal | None:
        opening_return_ticks = _finite_float(bar.get(slot["opening_return_column"]))
        opening_imbalance = _finite_float(bar.get(slot["opening_imbalance_column"]))
        opening_volume_rank = _finite_float(bar.get(slot["opening_volume_rank_column"]))
        session_return_ticks = _finite_float(bar.get(slot["session_return_column"]))
        session_delta_ratio = _finite_float(bar.get(slot["session_delta_ratio_column"]))
        price_vs_vwap_ticks = _finite_float(bar.get(slot["price_vs_vwap_column"]))
        if opening_return_ticks is None or opening_imbalance is None or opening_volume_rank is None:
            return None
        if opening_volume_rank < self.min_open_volume_rank:
            return None

        if self.mode == "opening_drive_flow_continuation":
            flow_sign = _aligned_opening_sign(
                opening_return_ticks,
                opening_imbalance,
                self.min_open_return_ticks,
                self.min_open_imbalance,
            )
            if flow_sign == 0 or session_return_ticks is None or session_delta_ratio is None:
                return None
            retrace_frac = flow_sign * session_return_ticks / max(abs(opening_return_ticks), 1.0)
            if retrace_frac < self.min_current_retrace_frac or retrace_frac > self.max_current_retrace_frac:
                return None
            if flow_sign * session_delta_ratio < self.min_session_delta_ratio:
                return None
            direction = _direction_from_flow(flow_sign, fade=False)
        elif self.mode == "opening_absorption_fade":
            flow_sign = _opening_imbalance_sign(opening_imbalance, self.min_open_imbalance)
            if flow_sign == 0 or abs(opening_return_ticks) > self.max_open_return_ticks:
                return None
            if price_vs_vwap_ticks is not None and flow_sign * price_vs_vwap_ticks < self.min_vwap_extension_ticks:
                return None
            retrace_frac = (
                flow_sign * session_return_ticks / max(abs(opening_return_ticks), 1.0)
                if session_return_ticks is not None
                else None
            )
            direction = _direction_from_flow(flow_sign, fade=True)
        elif self.mode == "opening_price_flow_divergence_fade":
            flow_sign = _opening_price_sign(opening_return_ticks, self.min_open_return_ticks)
            if flow_sign == 0 or abs(opening_imbalance) > self.max_abs_open_imbalance:
                return None
            if price_vs_vwap_ticks is not None and flow_sign * price_vs_vwap_ticks < self.min_vwap_extension_ticks:
                return None
            retrace_frac = (
                flow_sign * session_return_ticks / max(abs(opening_return_ticks), 1.0)
                if session_return_ticks is not None
                else None
            )
            direction = _direction_from_flow(flow_sign, fade=True)
        else:
            raise ValueError(f"Unsupported opening orderflow mode: {self.mode}.")

        current_close = float(bar["close"])
        report_fields = {
            "academic_source_key": "cont_kukanov_stoikov_ofi_and_trade_information_content",
            "setup_mode": slot["setup_mode"],
            "slot_id": slot["slot_id"],
            "feature_method": "sierra_bar_opening_orderflow_drive",
            "orderflow_regime_mode": self.mode,
            "opening_return_column": slot["opening_return_column"],
            "opening_return_ticks": opening_return_ticks,
            "opening_imbalance_column": slot["opening_imbalance_column"],
            "opening_imbalance": opening_imbalance,
            "opening_volume_rank_column": slot["opening_volume_rank_column"],
            "opening_volume_rank": opening_volume_rank,
            "flow_sign": flow_sign,
            "session_return_column": slot["session_return_column"],
            "session_return_ticks": session_return_ticks,
            "session_delta_ratio_column": slot["session_delta_ratio_column"],
            "session_delta_ratio": session_delta_ratio,
            "price_vs_vwap_column": slot["price_vs_vwap_column"],
            "price_vs_vwap_ticks": price_vs_vwap_ticks,
            "min_open_return_ticks": self.min_open_return_ticks,
            "max_open_return_ticks": self.max_open_return_ticks,
            "min_open_imbalance": self.min_open_imbalance,
            "max_abs_open_imbalance": self.max_abs_open_imbalance,
            "min_open_volume_rank": self.min_open_volume_rank,
            "min_current_retrace_frac": self.min_current_retrace_frac,
            "max_current_retrace_frac": self.max_current_retrace_frac,
            "min_session_delta_ratio": self.min_session_delta_ratio,
            "min_vwap_extension_ticks": self.min_vwap_extension_ticks,
            "current_retrace_frac": retrace_frac,
            "orderflow_signal_timestamp": signal_timestamp,
            "orderflow_intended_entry_timestamp": signal_timestamp,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": slot["flatten_time"].strftime("%H:%M:%S"),
            "swept_level": current_close,
            "sweep_timestamp": timestamp,
            "sweep_high": float(bar["high"]),
            "sweep_low": float(bar["low"]),
            "reclaim_timestamp": signal_timestamp,
        }
        return Signal(
            direction=direction,
            level_type=f"orderflow_regime_{slot['setup_mode']}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": slot["setup_mode"],
                "slot_id": slot["slot_id"],
                "mode": self.mode,
                "opening_return_ticks": opening_return_ticks,
                "opening_imbalance": opening_imbalance,
                "opening_volume_rank": opening_volume_rank,
                "flow_sign": flow_sign,
                "current_retrace_frac": retrace_frac,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": slot["flatten_time"].strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _validate(self) -> None:
        if self.mode not in {
            "flow_impulse_continuation",
            "flow_impulse_reversal",
            "absorption_exhaustion_reversal",
            "toxicity_regime_continuation",
            "toxicity_regime_reversal",
            "prior_inventory_reversion",
            *_OPENING_DRIVE_MODES,
        }:
            raise ValueError("Unsupported orderflow_regime mode.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if not (0.5 <= self.pressure_rank_threshold <= 1.0):
            raise ValueError("pressure_rank_threshold must be in [0.5, 1.0].")
        if not (0.0 <= self.toxicity_rank_threshold <= 1.0):
            raise ValueError("toxicity_rank_threshold must be in [0, 1].")
        if self.min_return_ticks < 0 or self.max_abs_return_ticks < 0:
            raise ValueError("return thresholds must be non-negative.")
        if self.min_open_return_ticks < 0 or self.max_open_return_ticks < 0:
            raise ValueError("opening return thresholds must be non-negative.")
        if self.min_open_imbalance < 0 or self.max_abs_open_imbalance < 0:
            raise ValueError("opening imbalance thresholds must be non-negative.")
        if not (0.0 <= self.min_open_volume_rank <= 1.0):
            raise ValueError("min_open_volume_rank must be in [0, 1].")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")


def _slot_config(params: dict, slot: dict, index: int) -> dict:
    merged = {**params, **dict(slot or {})}
    merged.pop("slots", None)
    slot_id = str(merged.get("slot_id", f"slot_{index}"))
    setup_mode = str(merged.get("setup_mode", slot_id))
    return {
        "slot_id": slot_id,
        "setup_mode": setup_mode,
        "entry_time": parse_time(merged.get("entry_time", "10:00:00")),
        "flatten_time": parse_time(merged.get("flatten_time", params.get("flatten_time", "15:31:00"))),
        "pressure_rank_column": str(merged.get("pressure_rank_column", "trade_orderflow_imbalance_15_rank42")),
        "pressure_value_column": str(merged.get("pressure_value_column", "trade_orderflow_imbalance_15")),
        "toxicity_rank_column": str(
            merged.get("toxicity_rank_column", "trade_orderflow_signed_toxicity_15_rank42")
        ),
        "toxicity_value_column": str(
            merged.get("toxicity_value_column", "trade_orderflow_signed_toxicity_15")
        ),
        "effort_rank_column": merged.get("effort_rank_column"),
        "effort_rank_threshold": float(merged.get("effort_rank_threshold", 0.75)),
        "return_column": str(merged.get("return_column", "trade_orderflow_return_ticks_15")),
        "min_return_ticks": float(merged.get("min_return_ticks", params.get("min_return_ticks", 0.0))),
        "opening_return_column": str(
            merged.get("opening_return_column", "trade_orderflow_opening_return_ticks_30m")
        ),
        "opening_imbalance_column": str(
            merged.get("opening_imbalance_column", "trade_orderflow_opening_imbalance_30m")
        ),
        "opening_volume_rank_column": str(
            merged.get("opening_volume_rank_column", "trade_orderflow_opening_volume_rank42_30m")
        ),
        "session_return_column": str(
            merged.get("session_return_column", "trade_orderflow_session_return_ticks")
        ),
        "session_delta_ratio_column": str(
            merged.get("session_delta_ratio_column", "trade_orderflow_session_cum_delta_ratio")
        ),
        "price_vs_vwap_column": str(
            merged.get("price_vs_vwap_column", "trade_orderflow_price_vs_vwap_ticks")
        ),
    }


def _flow_sign_from_rank(rank: float, threshold: float) -> int:
    if rank >= threshold:
        return 1
    if rank <= (1.0 - threshold):
        return -1
    return 0


def _direction_from_flow(flow_sign: int, *, fade: bool) -> str:
    if fade:
        return "short" if flow_sign > 0 else "long"
    return "long" if flow_sign > 0 else "short"


def _return_confirms(return_ticks: float, flow_sign: int, min_return_ticks: float) -> bool:
    if flow_sign > 0:
        return return_ticks >= min_return_ticks
    return return_ticks <= -min_return_ticks


def _aligned_opening_sign(
    return_ticks: float,
    imbalance: float,
    min_return_ticks: float,
    min_imbalance: float,
) -> int:
    if return_ticks >= min_return_ticks and imbalance >= min_imbalance:
        return 1
    if return_ticks <= -min_return_ticks and imbalance <= -min_imbalance:
        return -1
    return 0


def _opening_imbalance_sign(imbalance: float, min_imbalance: float) -> int:
    if imbalance >= min_imbalance:
        return 1
    if imbalance <= -min_imbalance:
        return -1
    return 0


def _opening_price_sign(return_ticks: float, min_return_ticks: float) -> int:
    if return_ticks >= min_return_ticks:
        return 1
    if return_ticks <= -min_return_ticks:
        return -1
    return 0


def _session_timestamp(timestamp: pd.Timestamp, session_time) -> pd.Timestamp:
    return timestamp.replace(
        hour=session_time.hour,
        minute=session_time.minute,
        second=session_time.second,
        microsecond=0,
    )


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
