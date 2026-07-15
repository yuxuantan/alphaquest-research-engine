from __future__ import annotations


def opening_range_extension_target(signal, direction: str, extension_fraction: float = 0.5) -> float:
    high = _signal_value(signal, "opening_range_high", "sweep_high")
    low = _signal_value(signal, "opening_range_low", "sweep_low")
    width = _signal_value(signal, "opening_range_width", None)
    if width is None:
        width = high - low
    extension = float(width) * float(extension_fraction)
    if direction == "long":
        return high + extension
    return low - extension


class OpeningRangeExtensionTarget:
    name = "opening_range_extension"

    def __init__(self, params: dict):
        self.params = params

    def price(self, entry_price: float, stop_price: float, direction: str, signal=None) -> float:
        if signal is None:
            raise ValueError("opening_range_extension target requires the entry signal.")
        return opening_range_extension_target(
            signal,
            direction,
            float(self.params.get("extension_fraction", 0.5)),
        )


def _signal_value(signal, primary: str, fallback: str | None) -> float | None:
    value = getattr(signal, primary, None)
    if value is None and fallback is not None:
        value = getattr(signal, fallback)
    if value is None:
        return None
    return float(value)
