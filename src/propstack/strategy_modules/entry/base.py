from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Signal:
    direction: str
    level_type: str
    swept_level: float
    sweep_timestamp: object
    sweep_high: float
    sweep_low: float
    reclaim_timestamp: object
