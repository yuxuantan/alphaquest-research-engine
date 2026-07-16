from __future__ import annotations

import hashlib
import json
import math

import pandas as pd

from alphaquest.authoring.bar_rules import SafeBarRuleEvaluator, referenced_features, validate_bar_rule
from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.metadata import StrategyModuleMetadata
from alphaquest.utils.time import parse_time


class SafeBarRuleEntry:
    """Certified visual-rule entry evaluated after completed bars only."""

    name = "safe_bar_rule"
    required_columns = frozenset({"timestamp", "open", "high", "low", "close", "volume", "is_rth"})
    decision_timing = "bar_close"
    required_detail_granularity = None
    warmup_bars = 0
    metadata = StrategyModuleMetadata(
        name=name,
        module_type="entry",
        required_columns=required_columns,
        decision_timing=decision_timing,
        required_detail_granularity=required_detail_granularity,
        warmup_bars=warmup_bars,
        params_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["rule"],
            "properties": {
                "rule": {"type": "object"},
                "tunable_values": {"type": "object"},
                "certified_features": {"type": "array", "items": {"type": "string"}},
                "bar_interval_minutes": {"type": "number", "exclusiveMinimum": 0},
            },
        },
    )

    def __init__(self, params: dict):
        unknown = set(params) - {"rule", "tunable_values", "certified_features", "bar_interval_minutes"}
        if unknown:
            raise ValueError("safe_bar_rule received unknown parameters: " + ", ".join(sorted(unknown)))
        if "rule" not in params:
            raise ValueError("safe_bar_rule requires entry.params.rule")
        certified_features = {str(item) for item in params.get("certified_features") or []}
        self.rule = validate_bar_rule(params["rule"], certified_features=certified_features)
        injected_interval = float(params.get("bar_interval_minutes", self.rule.bar_interval_minutes))
        if not math.isclose(injected_interval, self.rule.bar_interval_minutes):
            raise ValueError(
                "safe_bar_rule rule.bar_interval_minutes must match the variant timeframe"
            )
        self.evaluator = SafeBarRuleEvaluator(
            self.rule,
            certified_features=certified_features,
            tunable_values=params.get("tunable_values") or {},
        )
        self.signal_start = parse_time(self.rule.signal_start_time)
        self.signal_end = parse_time(self.rule.signal_end_time)
        self.rule_hash = hashlib.sha256(
            json.dumps(
                self.rule.model_dump(mode="json", by_alias=True),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if self.rule.rth_only and not bool(bar.get("is_rth", False)):
            return None
        direction = self.evaluator.evaluate(bar.to_dict())
        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.rule.bar_interval_minutes)
        if not (self.signal_start <= bar_close.time() < self.signal_end):
            return None
        if trades_today >= self.rule.max_trades_per_day or direction is None:
            return None

        close = float(bar["close"])
        report_fields = {
            "safe_bar_rule_hash": self.rule_hash,
            "safe_bar_rule_signal_timestamp": bar_close,
            "safe_bar_rule_direction": direction,
            "safe_bar_rule_features": sorted(referenced_features(self.rule)),
        }
        return Signal(
            direction=direction,
            level_type="safe_bar_rule_completed_bar",
            swept_level=close,
            sweep_timestamp=bar_close,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=bar_close,
            metadata={
                "confirmation_high": float(bar["high"]),
                "confirmation_low": float(bar["low"]),
                "confirmation_close": close,
                "safe_bar_rule_hash": self.rule_hash,
            },
            report_fields=report_fields,
        )


__all__ = ["SafeBarRuleEntry"]
