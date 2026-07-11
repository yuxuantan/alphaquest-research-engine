from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StrategyModuleMetadata:
    name: str
    module_type: str
    required_columns: frozenset[str] = field(default_factory=frozenset)
    decision_timing: str = "bar_close"
    required_detail_granularity: str | None = None
    warmup_bars: int = 0
    params_schema: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "module_type": self.module_type,
            "required_columns": sorted(self.required_columns),
            "decision_timing": self.decision_timing,
            "required_detail_granularity": self.required_detail_granularity,
            "warmup_bars": self.warmup_bars,
            "params_schema": self.params_schema,
        }


def metadata_from_module_class(module_type: str, module_cls: type) -> StrategyModuleMetadata:
    raw = getattr(module_cls, "metadata", None)
    if isinstance(raw, StrategyModuleMetadata):
        return raw
    if isinstance(raw, dict):
        return StrategyModuleMetadata(
            name=str(raw.get("name") or getattr(module_cls, "name", module_cls.__name__)),
            module_type=str(raw.get("module_type") or module_type),
            required_columns=frozenset(str(item) for item in raw.get("required_columns") or ()),
            decision_timing=str(raw.get("decision_timing") or "bar_close"),
            required_detail_granularity=raw.get("required_detail_granularity"),
            warmup_bars=int(raw.get("warmup_bars") or 0),
            params_schema=dict(raw.get("params_schema") or {}),
        )
    return StrategyModuleMetadata(
        name=str(getattr(module_cls, "name", module_cls.__name__)),
        module_type=module_type,
        required_columns=frozenset(str(item) for item in getattr(module_cls, "required_columns", ()) or ()),
        decision_timing=str(getattr(module_cls, "decision_timing", "bar_close")),
        required_detail_granularity=getattr(module_cls, "required_detail_granularity", None),
        warmup_bars=int(getattr(module_cls, "warmup_bars", 0) or 0),
        params_schema=dict(getattr(module_cls, "params_schema", {}) or {}),
    )
