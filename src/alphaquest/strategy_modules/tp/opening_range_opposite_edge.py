from __future__ import annotations


def opening_range_opposite_edge_target(signal, direction: str) -> float:
    if direction == "long":
        return _signal_value(signal, "opening_range_high", "sweep_high")
    return _signal_value(signal, "opening_range_low", "sweep_low")


class OpeningRangeOppositeEdgeTarget:
    name = "opening_range_opposite_edge"

    def __init__(self, params: dict):
        self.params = params

    def price(self, entry_price: float, stop_price: float, direction: str, signal=None) -> float:
        if signal is None:
            raise ValueError("opening_range_opposite_edge target requires the entry signal.")
        return opening_range_opposite_edge_target(signal, direction)


def _signal_value(signal, primary: str, fallback: str) -> float:
    value = getattr(signal, primary, None)
    if value is None:
        value = getattr(signal, fallback)
    return float(value)
