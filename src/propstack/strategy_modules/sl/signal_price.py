from __future__ import annotations

import math


class SignalPriceStop:
    name = "signal_price"

    def __init__(self, params: dict):
        self.params = params
        self.metadata_key = str(params.get("metadata_key", "signal_stop_price"))
        self.round_to_tick = bool(params.get("round_to_tick", True))

    def price(self, signal, direction: str, tick_size: float, entry_price: float | None = None) -> float | None:
        if signal is None:
            return None
        value = getattr(signal, "metadata", {}).get(self.metadata_key)
        stop = _finite_float(value)
        if stop is None:
            return None
        if entry_price is not None:
            entry = float(entry_price)
            if direction == "long" and stop >= entry:
                return None
            if direction == "short" and stop <= entry:
                return None
        if not self.round_to_tick:
            return stop
        return _round_price(stop, float(tick_size), "floor" if direction == "long" else "ceil")


def _round_price(price: float, tick_size: float, mode: str) -> float:
    if tick_size <= 0:
        return price
    scaled = price / tick_size
    if mode == "floor":
        return math.floor(scaled + 1e-12) * tick_size
    if mode == "ceil":
        return math.ceil(scaled - 1e-12) * tick_size
    raise ValueError(f"Unsupported rounding mode: {mode}")


def _finite_float(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
