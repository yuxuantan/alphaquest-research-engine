from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
import math
from typing import Any, Literal

from alphaquest.authoring.bar_rules import validate_bar_rule
from alphaquest.authoring.models import (
    DatasetManifestV1,
    ModuleBindingV1,
    ModuleManifestV1,
    ParameterSpecV1,
)


ModuleType = Literal["entry", "sl", "tp"]


class ModuleCatalogError(ValueError):
    """Raised when a Studio module binding is not certified or is malformed."""


class CertifiedModuleCatalog:
    def __init__(self, manifests: Iterable[ModuleManifestV1]) -> None:
        entries = list(manifests)
        keys = [(item.module_type, item.name) for item in entries]
        if len(set(keys)) != len(keys):
            raise ValueError("module catalog contains duplicate module names within a module type")
        self._manifests = {key: manifest for key, manifest in zip(keys, entries)}

    def get(self, module_type: ModuleType, name: str) -> ModuleManifestV1:
        try:
            manifest = self._manifests[(module_type, name)]
        except KeyError as exc:
            if _registered_module_class(module_type, name) is not None:
                raise ModuleCatalogError(f"{module_type} module {name!r} is developer-only") from exc
            raise ModuleCatalogError(f"unknown {module_type} module {name!r}") from exc
        if manifest.certification_status != "certified":
            raise ModuleCatalogError(f"{module_type} module {name!r} is developer-only")
        return manifest

    def certification_status(self, module_type: ModuleType, name: str) -> Literal["certified", "developer_only"]:
        if (module_type, name) in self._manifests:
            return "certified"
        if _registered_module_class(module_type, name) is not None:
            return "developer_only"
        raise ModuleCatalogError(f"unknown {module_type} module {name!r}")

    def describe(self, module_type: ModuleType, name: str) -> ModuleManifestV1:
        if (module_type, name) in self._manifests:
            return self._manifests[(module_type, name)]
        module_cls = _registered_module_class(module_type, name)
        if module_cls is None:
            raise ModuleCatalogError(f"unknown {module_type} module {name!r}")
        timing = str(getattr(module_cls, "decision_timing", "bar_close"))
        completed_bar = timing == "bar_close"
        return ModuleManifestV1(
            name=name,
            module_type=module_type,
            certification_status="developer_only",
            summary="Existing executable module; parameter and causal-data contract has not been certified for Studio.",
            decision_timing=(
                "completed_bar_close"
                if module_type == "entry" and completed_bar
                else "intrabar_or_event"
                if module_type == "entry"
                else "entry_price"
            ),
            required_columns=sorted(str(item) for item in getattr(module_cls, "required_columns", ()) or ()),
            required_detail_granularity=getattr(module_cls, "required_detail_granularity", None),
            parameters={},
            max_tunable_parameters=0,
            next_bar_entry=module_type == "entry" and completed_bar,
        )

    def all(self, module_type: ModuleType | None = None) -> tuple[ModuleManifestV1, ...]:
        values = [
            manifest
            for (kind, _), manifest in self._manifests.items()
            if module_type is None or kind == module_type
        ]
        return tuple(sorted(values, key=lambda item: (item.module_type, item.name)))

    def validate_binding(
        self,
        module_type: ModuleType,
        binding: ModuleBindingV1 | Mapping[str, Any],
        *,
        dataset: DatasetManifestV1 | None = None,
    ) -> ModuleBindingV1:
        parsed = binding if isinstance(binding, ModuleBindingV1) else ModuleBindingV1.model_validate(dict(binding))
        manifest = self.get(module_type, parsed.module)
        unknown = set(parsed.params) - set(manifest.parameters)
        if unknown:
            raise ModuleCatalogError(
                f"{module_type} module {parsed.module!r} has unknown parameters: {', '.join(sorted(unknown))}"
            )
        normalized = deepcopy(parsed.params)
        for name, spec in manifest.parameters.items():
            if name not in normalized:
                if spec.required and spec.default is None:
                    raise ModuleCatalogError(f"{module_type} module {parsed.module!r} requires parameter {name!r}")
                if spec.default is not None:
                    normalized[name] = deepcopy(spec.default)
            if name in normalized:
                _validate_parameter(name, normalized[name], spec)

        if parsed.module == "safe_bar_rule":
            certified = set(dataset.certified_features) if dataset is not None else set()
            supplied_certified = set(normalized.get("certified_features") or [])
            if supplied_certified and supplied_certified != certified:
                raise ModuleCatalogError(
                    "safe-rule certified_features must come from the selected dataset manifest"
                )
            normalized["certified_features"] = sorted(certified)
            rule = validate_bar_rule(normalized["rule"], certified_features=certified)
            normalized["rule"] = rule.model_dump(mode="json", by_alias=True)
            declared = {item.name: item for item in rule.tunables}
            values = dict(normalized.get("tunable_values") or {})
            unknown_values = set(values) - set(declared)
            if unknown_values:
                raise ModuleCatalogError("unknown safe-rule tunable values: " + ", ".join(sorted(unknown_values)))
            for name, definition in declared.items():
                values.setdefault(name, definition.default)
            normalized["tunable_values"] = values
            grid_names = {
                name.split(".", 1)[1]
                for name in parsed.parameter_grid
                if name.startswith("tunable_values.")
            }
            if grid_names != set(declared):
                missing = sorted(set(declared) - grid_names)
                extra = sorted(grid_names - set(declared))
                detail = []
                if missing:
                    detail.append("missing " + ", ".join(missing))
                if extra:
                    detail.append("unknown " + ", ".join(extra))
                raise ModuleCatalogError(
                    "safe-rule tunables and parameter_grid must match exactly: " + "; ".join(detail)
                )

        if len(parsed.parameter_grid) > manifest.max_tunable_parameters:
            raise ModuleCatalogError(
                f"{module_type} module {parsed.module!r} allows at most "
                f"{manifest.max_tunable_parameters} tunable parameter(s)"
            )
        for name, values in parsed.parameter_grid.items():
            if parsed.module == "safe_bar_rule" and name.startswith("tunable_values."):
                tunable_name = name.split(".", 1)[1]
                rule = validate_bar_rule(normalized["rule"], certified_features=set(dataset.certified_features) if dataset else set())
                definitions = {item.name: item for item in rule.tunables}
                if tunable_name not in definitions:
                    raise ModuleCatalogError(f"safe rule does not declare tunable {tunable_name!r}")
                expected = definitions[tunable_name].values
                if not _same_typed_values(values, expected):
                    raise ModuleCatalogError(
                        f"parameter grid for {tunable_name!r} must equal the values frozen in the rule"
                    )
                continue
            try:
                spec = manifest.parameters[name]
            except KeyError as exc:
                raise ModuleCatalogError(f"unknown tunable parameter {name!r} for {parsed.module!r}") from exc
            if not spec.tunable:
                raise ModuleCatalogError(f"parameter {name!r} is fixed and cannot be tuned")
            for value in values:
                _validate_parameter(name, value, spec)
        return ModuleBindingV1(module=parsed.module, params=normalized, parameter_grid=parsed.parameter_grid)


def get_certified_module_catalog() -> CertifiedModuleCatalog:
    return CERTIFIED_MODULE_CATALOG


def _parameter(
    value_type: Literal["boolean", "integer", "number", "string", "object", "array"],
    description: str,
    *,
    required: bool = False,
    default: Any = None,
    minimum: float | None = None,
    maximum: float | None = None,
    choices: list[Any] | None = None,
    tunable: bool = False,
) -> ParameterSpecV1:
    return ParameterSpecV1(
        value_type=value_type,
        description=description,
        required=required,
        default=default,
        minimum=minimum,
        maximum=maximum,
        choices=choices,
        tunable=tunable,
    )


def _manifest(
    name: str,
    module_type: ModuleType,
    summary: str,
    parameters: dict[str, ParameterSpecV1],
    *,
    required_columns: list[str] | None = None,
    max_tunables: int,
) -> ModuleManifestV1:
    entry = module_type == "entry"
    return ModuleManifestV1(
        name=name,
        module_type=module_type,
        certification_status="certified",
        summary=summary,
        decision_timing="completed_bar_close" if entry else "entry_price",
        required_columns=required_columns or [],
        required_detail_granularity="bars" if entry else None,
        parameters=parameters,
        max_tunable_parameters=max_tunables,
        next_bar_entry=entry,
    )


CERTIFIED_MODULE_CATALOG = CertifiedModuleCatalog(
    [
        ModuleManifestV1(
            name="yush_orderflow_range",
            module_type="entry",
            certification_status="certified",
            summary="Causal trade-event AOI, tap, reversal, and order-flow trigger state machine.",
            decision_timing="intrabar_or_event",
            required_columns=[
                "timestamp",
                "price",
                "size",
                "side",
                "signed_size",
                "contract_symbol",
            ],
            required_detail_granularity="trade_events",
            parameters={
                "mechanics": _parameter(
                    "object",
                    "Complete frozen mechanics mapping for the certified Yush event strategy.",
                    required=True,
                )
            },
            max_tunable_parameters=0,
            next_bar_entry=False,
        ),
        ModuleManifestV1(
            name="event_aoi_structural_stop",
            module_type="sl",
            certification_status="certified",
            summary="Use the event strategy's frozen AOI boundary, minimum breathing room, and risk cap.",
            decision_timing="entry_price",
            parameters={},
            max_tunable_parameters=0,
        ),
        ModuleManifestV1(
            name="event_value_area_management",
            module_type="tp",
            certification_status="certified",
            summary="Activate protected profit at the frozen midpoint and target the opposite value edge.",
            decision_timing="post_entry",
            parameters={},
            max_tunable_parameters=0,
        ),
        _manifest(
            "safe_bar_rule",
            "entry",
            "A bounded visual rule evaluated incrementally after each completed bar.",
            {
                "rule": _parameter("object", "Frozen alphaquest.bar-rule/v1 rule.", required=True),
                "tunable_values": _parameter("object", "Selected values for predeclared rule tunables.", default={}),
                "certified_features": _parameter(
                    "array", "Dataset features with separately reviewed causal timing.", default=[]
                ),
            },
            required_columns=["timestamp", "open", "high", "low", "close", "volume", "is_rth"],
            max_tunables=2,
        ),
        _manifest(
            "calendar_session_bias",
            "entry",
            "Emit a predeclared weekday direction at one completed-bar time.",
            {
                "signal_time": _parameter("string", "Completed-bar signal time.", default="09:35:00"),
                "bar_interval_minutes": _parameter("number", "Bar duration in minutes.", default=1.0, minimum=0.01),
                "max_trades_per_day": _parameter("integer", "Maximum entries per session.", default=1, minimum=1),
                "weekday_directions": _parameter("object", "Monday-zero weekday to long/short mapping.", required=True),
                "setup_mode": _parameter("string", "Report label for the frozen setup.", default="weekday_session_bias"),
            },
            required_columns=["timestamp", "session_date", "is_rth", "open", "high", "low", "close"],
            max_tunables=2,
        ),
        _manifest(
            "opening_range_breakout",
            "entry",
            "Trade a completed close beyond a previously completed opening range.",
            {
                "rth_start": _parameter("string", "RTH opening time.", default="09:30:00"),
                "opening_range_minutes": _parameter(
                    "number", "Opening-range duration.", default=5.0, minimum=1.0, tunable=True
                ),
                "confirmation_minutes": _parameter(
                    "number", "Completed breakout confirmation duration.", default=5.0, minimum=1.0, tunable=True
                ),
                "bar_interval_minutes": _parameter("number", "Bar duration in minutes.", default=1.0, minimum=0.01),
                "last_entry_time": _parameter("string", "Exclusive entry cutoff.", default="12:00:00"),
                "max_opening_range_pct_of_open": _parameter(
                    "number", "Maximum accepted range width divided by open.", default=0.0055, minimum=0.0, tunable=True
                ),
                "allow_long": _parameter("boolean", "Permit upside breakouts.", default=True),
                "allow_short": _parameter("boolean", "Permit downside breakouts.", default=True),
                "skip_tuesday_longs": _parameter("boolean", "Disable Tuesday upside signals.", default=True),
                "max_trades_per_day": _parameter("integer", "Maximum entries per session.", default=1, minimum=1),
            },
            required_columns=["timestamp", "session_date", "is_rth", "open", "high", "low", "close"],
            max_tunables=2,
        ),
        _manifest(
            "daily_time_series_momentum",
            "entry",
            "Trade the direction of a trend built only from prior completed RTH closes.",
            {
                "setup_mode": _parameter(
                    "string",
                    "Frozen trend mechanic.",
                    default="close_to_close_trend",
                    choices=["close_to_close_trend", "volatility_normalized_trend", "short_term_alignment"],
                ),
                "rth_end": _parameter("string", "Time at which a completed daily close is recorded.", default="16:00:00"),
                "signal_time": _parameter("string", "Completed-bar signal time.", default="10:00:00"),
                "bar_interval_minutes": _parameter("number", "Bar duration in minutes.", default=1.0, minimum=0.01),
                "lookback_sessions": _parameter(
                    "integer", "Prior-session trend lookback.", default=20, minimum=2, tunable=True
                ),
                "confirmation_sessions": _parameter(
                    "integer", "Prior-session confirmation lookback.", default=1, minimum=1, tunable=True
                ),
                "min_abs_trend_return_pct": _parameter(
                    "number", "Minimum absolute trend return.", default=0.0, minimum=0.0, tunable=True
                ),
                "min_trend_zscore": _parameter(
                    "number", "Minimum absolute normalized trend score.", default=0.0, minimum=0.0, tunable=True
                ),
                "max_trades_per_day": _parameter("integer", "Maximum entries per session.", default=1, minimum=1),
                "allow_long": _parameter("boolean", "Permit positive-trend signals.", default=True),
                "allow_short": _parameter("boolean", "Permit negative-trend signals.", default=True),
            },
            required_columns=["timestamp", "session_date", "is_rth", "open", "high", "low", "close"],
            max_tunables=2,
        ),
        _manifest(
            "points_from_entry",
            "sl",
            "Place the stop a fixed number of points from actual entry price.",
            {
                "stop_points": _parameter("number", "Positive stop distance in points.", default=1.0, minimum=0.000001, tunable=True),
                "round_to_tick": _parameter("boolean", "Round away from entry to a legal tick.", default=True),
            },
            max_tunables=1,
        ),
        _manifest(
            "percent_from_entry",
            "sl",
            "Place the stop a fixed percentage from actual entry price.",
            {
                "stop_pct": _parameter("number", "Positive stop distance as a decimal fraction.", default=0.002, minimum=0.000001, tunable=True),
                "round_to_tick": _parameter("boolean", "Round away from entry to a legal tick.", default=True),
            },
            max_tunables=1,
        ),
        _manifest(
            "fixed_dollar_per_contract",
            "sl",
            "Cap loss using fixed dollars per contract and the configured tick value.",
            {
                "dollars_per_contract": _parameter(
                    "number", "Positive dollar risk per contract.", required=True, minimum=0.01, tunable=True
                ),
                "tick_value": _parameter("number", "Instrument tick value.", required=True, minimum=0.000001),
                "round_to_tick": _parameter("boolean", "Round away from entry to a legal tick.", default=True),
            },
            max_tunables=1,
        ),
        _manifest(
            "fixed_r",
            "tp",
            "Place the target at a fixed multiple of initial stop risk.",
            {
                "target_r_multiple": _parameter("number", "Reward-to-risk multiple.", default=1.5, minimum=1.0, tunable=True),
            },
            max_tunables=1,
        ),
        _manifest(
            "cost_adjusted_fixed_r",
            "tp",
            "Place the target at a cost-adjusted multiple of initial stop risk.",
            {
                "target_r_multiple": _parameter("number", "After-cost reward-to-risk multiple.", default=1.0, minimum=1.0, tunable=True),
                "tick_size": _parameter("number", "Instrument tick size.", default=0.25, minimum=0.000001),
                "tick_value": _parameter("number", "Instrument tick value.", default=12.5, minimum=0.000001),
                "commission_per_contract": _parameter("number", "One-way commission per contract.", default=0.0, minimum=0.0),
                "slippage_ticks": _parameter("number", "One-way slippage in ticks.", default=0.0, minimum=0.0),
                "round_to_tick": _parameter("boolean", "Round target to a legal tick.", default=True),
            },
            max_tunables=1,
        ),
    ]
)


def _validate_parameter(name: str, value: Any, spec: ParameterSpecV1) -> None:
    valid_type = {
        "boolean": type(value) is bool,
        "integer": type(value) is int,
        "number": type(value) in {int, float} and not isinstance(value, bool),
        "string": type(value) is str,
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
    }[spec.value_type]
    if not valid_type:
        raise ModuleCatalogError(f"parameter {name!r} must be {spec.value_type}")
    if type(value) in {int, float} and not isinstance(value, bool):
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ModuleCatalogError(f"parameter {name!r} must be finite")
        if spec.minimum is not None and numeric < spec.minimum:
            raise ModuleCatalogError(f"parameter {name!r} must be >= {spec.minimum}")
        if spec.maximum is not None and numeric > spec.maximum:
            raise ModuleCatalogError(f"parameter {name!r} must be <= {spec.maximum}")
    if spec.choices is not None and not any(type(value) is type(item) and value == item for item in spec.choices):
        raise ModuleCatalogError(f"parameter {name!r} must be one of {spec.choices!r}")


def _same_typed_values(left: list[Any], right: list[Any]) -> bool:
    return len(left) == len(right) and all(
        type(a) is type(b) and a == b for a, b in zip(left, right)
    )


def _registered_module_class(module_type: ModuleType, name: str) -> type | None:
    # Lazy imports keep the catalog usable by the safe_bar_rule module while the
    # entry registry itself is still being initialized.
    if module_type == "entry":
        from alphaquest.strategy_modules.entry import ENTRY_MODULES

        return ENTRY_MODULES.get(name)
    if module_type == "sl":
        from alphaquest.strategy_modules.sl import SL_MODULES

        return SL_MODULES.get(name)
    from alphaquest.strategy_modules.tp import TP_MODULES

    return TP_MODULES.get(name)


__all__ = [
    "CERTIFIED_MODULE_CATALOG",
    "CertifiedModuleCatalog",
    "ModuleCatalogError",
    "get_certified_module_catalog",
]
