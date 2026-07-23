"""Certified strategies for the canonical trade-event replay lane."""

from __future__ import annotations

from typing import Any

from alphaquest.strategy_certification import (
    load_strategy_certifications,
    normalize_certified_event_params,
    resolve_factory,
    strategy_identity_for_config,
)
from alphaquest.strategy_modules.event.yush_orderflow_range import (
    YushOrderflowRangeConfig,
    YushOrderflowRangeEventStrategy,
)


def _certifications():
    return load_strategy_certifications(require_current=True)


def certified_event_strategy_names() -> set[str]:
    return set(_certifications())


def certified_event_entry_modules() -> set[str]:
    return {item.entry_module for item in _certifications().values()}


def certified_event_sl_modules() -> set[str]:
    return {item.stop_module for item in _certifications().values()}


def certified_event_tp_modules() -> set[str]:
    return {item.target_module for item in _certifications().values()}


def build_event_strategy(config: dict[str, Any]):
    strategy = config.get("strategy") or {}
    declaration = strategy.get("event") or {}
    name = str(declaration.get("module") or strategy.get("strategy_name") or config.get("strategy_name") or "")
    certification = strategy_identity_for_config(config, require_declared_match=True)
    if certification is None or certification.strategy_id != name:
        raise ValueError(f"unknown certified event strategy: {name!r}")
    params = declaration.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError("strategy.event.params must be a mapping")
    normalized = normalize_certified_event_params(certification, dict(params))
    return resolve_factory(certification.factory)(normalized)


__all__ = [
    "YushOrderflowRangeConfig",
    "YushOrderflowRangeEventStrategy",
    "build_event_strategy",
    "certified_event_entry_modules",
    "certified_event_sl_modules",
    "certified_event_strategy_names",
    "certified_event_tp_modules",
]
