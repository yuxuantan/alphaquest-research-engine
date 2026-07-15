from __future__ import annotations

import math


class GapFillFractionTarget:
    name = "gap_fill_fraction"

    def __init__(self, params: dict):
        self.params = params

    def price(self, entry_price: float, stop_price: float, direction: str, signal=None) -> float:
        prev_close = _signal_value(signal, "prev_rth_close")
        fill_fraction = float(self.params.get("fill_fraction", 1.0))
        tick_size = float(self.params.get("tick_size", 0.25))
        if prev_close is None or tick_size <= 0 or not math.isfinite(fill_fraction):
            return float("nan")
        entry = float(entry_price)
        target = entry + (prev_close - entry) * fill_fraction
        if direction == "long":
            return math.floor(target / tick_size) * tick_size
        if direction == "short":
            return math.ceil(target / tick_size) * tick_size
        return float("nan")


def _signal_value(signal, key: str) -> float | None:
    if signal is None:
        return None
    for source_name in ("report_fields", "metadata"):
        source = getattr(signal, source_name, None)
        if isinstance(source, dict) and key in source:
            try:
                value = float(source[key])
            except (TypeError, ValueError):
                return None
            return value if math.isfinite(value) else None
    return None
