from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date
from collections.abc import Mapping
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Identifier = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_]*$")]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Scalar = Union[bool, int, float, str]

BUILTIN_BAR_FEATURES = frozenset({"open", "high", "low", "close", "volume", "is_rth"})
CERTIFIED_RECIPE_BINDINGS: dict[str, tuple[str, str | None]] = {
    "calendar_session_bias": ("calendar_session_bias", None),
    "opening_range_breakout": ("opening_range_breakout", None),
    "daily_tsm_close_to_close": ("daily_time_series_momentum", "close_to_close_trend"),
    "daily_tsm_volatility_normalized": (
        "daily_time_series_momentum",
        "volatility_normalized_trend",
    ),
    "daily_tsm_short_term_alignment": (
        "daily_time_series_momentum",
        "short_term_alignment",
    ),
}
_TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d$")


class StrictAuthoringModel(BaseModel):
    """Base for Studio-owned contracts.

    Existing campaign YAML remains intentionally permissive.  These contracts are
    strict because they are the trust boundary between a no-code draft and the
    executable research tree.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True, strict=True, populate_by_name=True)


class ResearchSourceV1(StrictAuthoringModel):
    title: Annotated[str, Field(min_length=1)]
    authors: Annotated[list[str], Field(min_length=1)]
    year: Annotated[int, Field(ge=1900, le=2200)]
    link: str | None = None
    doi: str | None = None
    relevance: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def require_locator(self) -> "ResearchSourceV1":
        if not self.link and not self.doi:
            raise ValueError("a research source must provide link or doi")
        return self


class EconomicEdgeFingerprintV1(StrictAuthoringModel):
    market_behavior: Annotated[str, Field(min_length=1)]
    causal_mechanism: Annotated[str, Field(min_length=1)]
    signal_inputs: Annotated[list[str], Field(min_length=1)]
    market_context: Annotated[str, Field(min_length=1)]
    holding_period: Annotated[str, Field(min_length=1)]


class DuplicateReviewV1(StrictAuthoringModel):
    reviewed_campaign_ids: list[Identifier] = Field(default_factory=list)
    ledger_queries: Annotated[list[str], Field(min_length=1)]
    conclusion: Literal["distinct", "duplicate", "needs_review"]
    substantive_distinction: Annotated[str, Field(min_length=1)]


class ParameterSpecV1(StrictAuthoringModel):
    value_type: Literal["boolean", "integer", "number", "string", "object", "array"]
    required: bool = False
    default: Any = None
    minimum: float | None = None
    maximum: float | None = None
    choices: list[Scalar] | None = None
    tunable: bool = False
    description: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_bounds(self) -> "ParameterSpecV1":
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum cannot exceed maximum")
        return self


class ModuleManifestV1(StrictAuthoringModel):
    schema_version: Literal["alphaquest.module-manifest/v1"] = Field(
        default="alphaquest.module-manifest/v1", alias="schema"
    )
    name: Identifier
    module_type: Literal["entry", "sl", "tp"]
    certification_status: Literal["certified", "developer_only"]
    summary: Annotated[str, Field(min_length=1)]
    decision_timing: Literal["completed_bar_close", "entry_price", "post_entry", "intrabar_or_event"]
    required_columns: list[str] = Field(default_factory=list)
    required_detail_granularity: str | None = None
    supported_symbols: Annotated[list[Literal["ES", "NQ"]], Field(min_length=1)] = Field(
        default_factory=lambda: ["ES", "NQ"]
    )
    parameters: dict[str, ParameterSpecV1] = Field(default_factory=dict)
    max_tunable_parameters: Annotated[int, Field(ge=0, le=2)] = 0
    next_bar_entry: bool = False

    @model_validator(mode="after")
    def certified_modules_are_causal(self) -> "ModuleManifestV1":
        if self.certification_status == "certified" and self.module_type == "entry":
            if self.decision_timing != "completed_bar_close" or not self.next_bar_entry:
                raise ValueError("certified entry modules must decide at completed-bar close for next-bar entry")
            if self.required_detail_granularity not in (None, "bars"):
                raise ValueError("Studio v1 entry modules may require completed bars only")
        return self


class DatasetManifestV1(StrictAuthoringModel):
    schema_version: Literal["alphaquest.dataset-manifest/v1"] = Field(
        default="alphaquest.dataset-manifest/v1", alias="schema"
    )
    dataset_id: Identifier
    source: Literal["csv", "parquet"]
    path: Annotated[str, Field(min_length=1)]
    symbol: Literal["ES", "NQ"]
    timeframe: Annotated[str, Field(pattern=r"^[1-9]\d*[mhd]$")]
    timezone: Annotated[str, Field(min_length=1)]
    exchange_timezone: Annotated[str, Field(min_length=1)]
    timestamp_semantics: Literal["bar_open", "bar_close"]
    source_timestamp_semantics: Literal["bar_open", "bar_close"] | None = None
    source_sha256: Sha256
    canonical_sha256: Sha256
    coverage_start: Annotated[str, Field(min_length=1)]
    coverage_end: Annotated[str, Field(min_length=1)]
    roll_policy: Annotated[str, Field(min_length=1)]
    continuous_contract: Literal[
        "none",
        "dominant_session_volume",
        "session_volume",
        "explicit_roll_calendar",
    ] = "none"
    contract_column: Literal["contract_symbol"] | None = None
    source_contract_column: str | None = None
    contract_count: Annotated[int, Field(ge=0)] = 1
    roll_calendar: str | None = None
    roll_calendar_sha256: Sha256 | None = None
    transformations: list[str] = Field(default_factory=list)
    row_count: Annotated[int, Field(ge=1)]
    dropped_row_count: Annotated[int, Field(ge=0)] = 0
    gap_count: Annotated[int, Field(ge=0)] = 0
    duplicate_count: Annotated[int, Field(ge=0)] = 0
    out_of_order_count: Annotated[int, Field(ge=0)] = 0
    invalid_ohlc_count: Annotated[int, Field(ge=0)] = 0
    cadence_violation_count: Annotated[int, Field(ge=0)] = 0
    certified_features: list[str] = Field(default_factory=list)
    quality_verdict: Literal["PASS", "FAIL", "NEEDS MANUAL REVIEW"]
    quality_notes: list[str] = Field(default_factory=list)

    @field_validator("certified_features")
    @classmethod
    def unique_certified_features(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("certified_features must be unique")
        return value

    @model_validator(mode="after")
    def fail_closed_quality(self) -> "DatasetManifestV1":
        defects = (
            self.duplicate_count
            + self.out_of_order_count
            + self.invalid_ohlc_count
            + self.cadence_violation_count
        )
        if self.quality_verdict == "PASS" and defects:
            raise ValueError("a dataset with duplicate, unordered, or invalid OHLC rows cannot have PASS quality")
        if self.quality_verdict == "PASS" and self.contract_count < 1:
            raise ValueError("a PASS dataset must identify at least one futures contract")
        if self.contract_count > 1 and self.contract_column != "contract_symbol":
            raise ValueError("multi-contract datasets must preserve canonical contract_symbol lineage")
        if self.quality_verdict == "PASS" and self.contract_count > 1 and self.continuous_contract == "none":
            raise ValueError("multi-contract datasets require an executable continuous-contract selection rule")
        if (
            self.quality_verdict == "PASS"
            and self.continuous_contract != "none"
            and self.contract_column != "contract_symbol"
        ):
            raise ValueError("continuous-contract selection requires canonical contract_symbol lineage")
        if self.continuous_contract == "explicit_roll_calendar" and not self.roll_calendar:
            raise ValueError("explicit_roll_calendar requires a governed roll_calendar path")
        if self.continuous_contract == "explicit_roll_calendar" and not self.roll_calendar_sha256:
            raise ValueError("explicit_roll_calendar requires a governed roll_calendar hash")
        if self.continuous_contract != "explicit_roll_calendar" and self.roll_calendar is not None:
            raise ValueError("roll_calendar is only valid with explicit_roll_calendar")
        if self.continuous_contract != "explicit_roll_calendar" and self.roll_calendar_sha256 is not None:
            raise ValueError("roll_calendar_sha256 is only valid with explicit_roll_calendar")
        return self


class FeatureValueV1(StrictAuthoringModel):
    source: Literal["feature"]
    name: Annotated[str, Field(min_length=1)]
    lag: Annotated[int, Field(ge=0, le=512)] = 0


class ConstantValueV1(StrictAuthoringModel):
    source: Literal["constant"]
    value: Scalar

    @field_validator("value")
    @classmethod
    def finite_number(cls, value: Scalar) -> Scalar:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("constant values must be finite")
        return value


class TunableValueV1(StrictAuthoringModel):
    source: Literal["tunable"]
    name: Identifier


class RollingValueV1(StrictAuthoringModel):
    source: Literal["rolling"]
    feature: Annotated[str, Field(min_length=1)]
    function: Literal["mean", "sum", "min", "max", "std"]
    window: Annotated[int, Field(ge=2, le=256)]
    lag: Annotated[int, Field(ge=0, le=512)] = 0
    min_periods: Annotated[int, Field(ge=1, le=256)] | None = None

    @model_validator(mode="after")
    def min_periods_within_window(self) -> "RollingValueV1":
        if self.min_periods is not None and self.min_periods > self.window:
            raise ValueError("min_periods cannot exceed window")
        return self


ValueExpressionV1 = Annotated[
    Union[FeatureValueV1, ConstantValueV1, TunableValueV1, RollingValueV1],
    Field(discriminator="source"),
]


class ComparisonConditionV1(StrictAuthoringModel):
    type: Literal["comparison"]
    operator: Literal["gt", "gte", "lt", "lte", "eq", "ne"]
    left: ValueExpressionV1
    right: ValueExpressionV1


class RangeConditionV1(StrictAuthoringModel):
    type: Literal["range"]
    value: ValueExpressionV1
    lower: ValueExpressionV1
    upper: ValueExpressionV1
    inclusive: bool = True


class CrossConditionV1(StrictAuthoringModel):
    type: Literal["cross"]
    direction: Literal["above", "below"]
    left: ValueExpressionV1
    right: ValueExpressionV1


class AllConditionV1(StrictAuthoringModel):
    type: Literal["all"]
    conditions: Annotated[list["ConditionV1"], Field(min_length=1, max_length=20)]


class AnyConditionV1(StrictAuthoringModel):
    type: Literal["any"]
    conditions: Annotated[list["ConditionV1"], Field(min_length=1, max_length=20)]


class NotConditionV1(StrictAuthoringModel):
    type: Literal["not"]
    condition: "ConditionV1"


ConditionV1 = Annotated[
    Union[
        ComparisonConditionV1,
        RangeConditionV1,
        CrossConditionV1,
        AllConditionV1,
        AnyConditionV1,
        NotConditionV1,
    ],
    Field(discriminator="type"),
]


class TunableDefinitionV1(StrictAuthoringModel):
    name: Identifier
    value_type: Literal["boolean", "integer", "number", "string"]
    values: Annotated[list[Scalar], Field(min_length=2, max_length=20)]
    default: Scalar

    @model_validator(mode="after")
    def validate_values(self) -> "TunableDefinitionV1":
        if len({_canonical_scalar(value) for value in self.values}) != len(self.values):
            raise ValueError(f"tunable {self.name!r} values must be unique")
        for value in [*self.values, self.default]:
            if not _matches_value_type(value, self.value_type):
                raise ValueError(f"tunable {self.name!r} requires {self.value_type} values")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"tunable {self.name!r} values must be finite")
        if _canonical_scalar(self.default) not in {_canonical_scalar(value) for value in self.values}:
            raise ValueError(f"tunable {self.name!r} default must be one of its declared values")
        return self


class BarRuleV1(StrictAuthoringModel):
    schema_version: Literal["alphaquest.bar-rule/v1"] = Field(default="alphaquest.bar-rule/v1", alias="schema")
    long_rule: ConditionV1 | None = None
    short_rule: ConditionV1 | None = None
    tunables: Annotated[list[TunableDefinitionV1], Field(max_length=2)] = Field(default_factory=list)
    rth_only: bool = True
    signal_start_time: str = "09:30:00"
    signal_end_time: str = "15:45:00"
    bar_interval_minutes: Annotated[float, Field(gt=0, le=1440)] = 1.0
    max_trades_per_day: Annotated[int, Field(ge=1, le=20)] = 1

    @field_validator("signal_start_time", "signal_end_time")
    @classmethod
    def valid_time(cls, value: str) -> str:
        if _TIME_PATTERN.fullmatch(value) is None:
            raise ValueError("time must use HH:MM:SS")
        return value

    @model_validator(mode="after")
    def validate_rule(self) -> "BarRuleV1":
        if self.long_rule is None and self.short_rule is None:
            raise ValueError("at least one of long_rule or short_rule is required")
        if self.signal_start_time >= self.signal_end_time:
            raise ValueError("signal_start_time must be earlier than signal_end_time")
        names = [item.name for item in self.tunables]
        if len(set(names)) != len(names):
            raise ValueError("tunable names must be unique")
        references = _condition_tunable_names(self.long_rule) | _condition_tunable_names(self.short_rule)
        undeclared = references - set(names)
        unused = set(names) - references
        if undeclared:
            raise ValueError(f"rule references undeclared tunables: {', '.join(sorted(undeclared))}")
        if unused:
            raise ValueError(f"rule declares unused tunables: {', '.join(sorted(unused))}")
        return self


class ModuleBindingV1(StrictAuthoringModel):
    module: Identifier
    params: dict[str, Any] = Field(default_factory=dict)
    parameter_grid: dict[str, Annotated[list[Scalar], Field(min_length=2, max_length=20)]] = Field(
        default_factory=dict
    )

    @field_validator("parameter_grid")
    @classmethod
    def unique_grid_values(cls, value: dict[str, list[Scalar]]) -> dict[str, list[Scalar]]:
        for name, values in value.items():
            if len({_canonical_scalar(item) for item in values}) != len(values):
                raise ValueError(f"parameter grid {name!r} contains duplicate values")
        return value


class VariantDraftV1(StrictAuthoringModel):
    schema_version: Literal["alphaquest.variant-draft/v1"] = Field(
        default="alphaquest.variant-draft/v1", alias="schema"
    )
    variant_id: Identifier
    title: Annotated[str, Field(min_length=1)]
    entry: ModuleBindingV1
    stop: ModuleBindingV1
    target: ModuleBindingV1
    mechanic_rationale: Annotated[str, Field(min_length=1)]
    entry_rationale: Annotated[str, Field(min_length=1)]
    stop_rationale: Annotated[str, Field(min_length=1)]
    target_rationale: Annotated[str, Field(min_length=1)]
    timeframe_session_rationale: Annotated[str, Field(min_length=1)]
    known_failure_modes: Annotated[list[str], Field(min_length=1)]
    material_difference: Annotated[str, Field(min_length=1)]
    confirmed: bool = False

    @model_validator(mode="after")
    def enforce_parameter_budget(self) -> "VariantDraftV1":
        budgets = (("entry", self.entry, 2), ("stop", self.stop, 1), ("target", self.target, 1))
        for label, binding, maximum in budgets:
            if len(binding.parameter_grid) > maximum:
                raise ValueError(f"{label} has more than {maximum} tunable parameter(s)")
        combinations = self.parameter_combinations
        if combinations != 1 and not 8 <= combinations <= 120:
            raise ValueError("parameter combinations must be exactly 1 or between 8 and 120")
        return self

    @property
    def parameter_combinations(self) -> int:
        product = 1
        for binding in (self.entry, self.stop, self.target):
            for values in binding.parameter_grid.values():
                product *= len(values)
        return product

    @property
    def mechanic_signature(self) -> str:
        structural = {
            "entry": _binding_structure(self.entry, "entry"),
            "stop": _binding_structure(self.stop, "stop"),
            "target": _binding_structure(self.target, "target"),
        }
        encoded = json.dumps(structural, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class ExecutionSettingsV1(StrictAuthoringModel):
    session_start: str = "09:30:00"
    session_end: str = "16:00:00"
    latest_entry_time: str = "15:45:00"
    flatten_time: str = "15:55:00"
    latest_flat_time: str = "15:56:00"
    overnight_allowed: Literal[False] = False
    initial_balance: Annotated[float, Field(gt=0)] = 150000.0
    tick_size: Annotated[float, Field(gt=0)]
    point_value: Annotated[float, Field(gt=0)]
    tick_value: Annotated[float, Field(gt=0)]
    commission_per_contract: Annotated[float, Field(ge=0)]
    slippage_ticks: Annotated[float, Field(ge=0)]
    contracts: Annotated[int, Field(ge=1)] = 1
    prop_profile: Annotated[str, Field(min_length=1)]

    @field_validator("session_start", "session_end", "latest_entry_time", "flatten_time", "latest_flat_time")
    @classmethod
    def valid_time(cls, value: str) -> str:
        if _TIME_PATTERN.fullmatch(value) is None:
            raise ValueError("time must use HH:MM:SS")
        return value

    @model_validator(mode="after")
    def validate_timeline(self) -> "ExecutionSettingsV1":
        if not (self.session_start < self.latest_entry_time < self.flatten_time <= self.latest_flat_time):
            raise ValueError("session/entry/flatten times are not in causal order")
        return self


class CampaignDraftV1(StrictAuthoringModel):
    schema_version: Literal["alphaquest.campaign-draft/v1"] = Field(
        default="alphaquest.campaign-draft/v1", alias="schema"
    )
    campaign_id: Identifier
    title: Annotated[str, Field(min_length=1)]
    created_at: str = Field(default_factory=lambda: date.today().isoformat(), pattern=r"^\d{4}-\d{2}-\d{2}$")
    instrument: Literal["ES", "NQ"]
    timeframe: Annotated[str, Field(pattern=r"^[1-9]\d*[mhd]$")]
    edge_family: Identifier
    hypothesis: Annotated[str, Field(min_length=1)]
    expected_mechanism: Annotated[str, Field(min_length=1)]
    holding_horizon: Annotated[str, Field(min_length=1)]
    known_failure_modes: Annotated[list[str], Field(min_length=1)]
    sources: Annotated[list[ResearchSourceV1], Field(min_length=1)]
    economic_edge_fingerprint: EconomicEdgeFingerprintV1
    duplicate_review: DuplicateReviewV1
    dataset: DatasetManifestV1
    execution: ExecutionSettingsV1
    variants: Annotated[list[VariantDraftV1], Field(min_length=5, max_length=5)]
    authoring_lane: Literal[
        "certified_recipe",
        "visual_completed_bar_rule",
        "engineering_handoff",
    ] = "certified_recipe"
    certified_recipe: Literal[
        "calendar_session_bias",
        "opening_range_breakout",
        "daily_tsm_close_to_close",
        "daily_tsm_volatility_normalized",
        "daily_tsm_short_term_alignment",
    ] | None = None
    engineering_handoff_path: str | None = None
    confirmation_context_sha256: Sha256 | None = None
    frozen: bool = False

    @model_validator(mode="after")
    def enforce_campaign_invariants(self) -> "CampaignDraftV1":
        if self.dataset.symbol != self.instrument:
            raise ValueError("dataset symbol must match campaign instrument")
        if self.dataset.timeframe != self.timeframe:
            raise ValueError("dataset timeframe must match campaign timeframe")
        ids = [variant.variant_id for variant in self.variants]
        if len(set(ids)) != 5:
            raise ValueError("campaign must contain exactly five unique variant IDs")
        signatures = [variant.mechanic_signature for variant in self.variants]
        if len(set(signatures)) != 5:
            raise ValueError("all five variants must have materially distinct, value-independent mechanics")
        if self.authoring_lane == "engineering_handoff":
            if not self.engineering_handoff_path:
                raise ValueError("engineering-handoff drafts must record their durable handoff path")
            if self.frozen:
                raise ValueError(
                    "engineering-handoff drafts cannot be frozen or published until a certified implementation exists"
                )
        if self.frozen:
            if self.authoring_lane == "certified_recipe":
                if not self.certified_recipe:
                    raise ValueError("the certified-recipe lane requires an explicit reviewed edge recipe")
                entry_module, setup_mode = CERTIFIED_RECIPE_BINDINGS[self.certified_recipe]
                for variant in self.variants:
                    if variant.entry.module != entry_module:
                        raise ValueError(
                            "all five certified-recipe variants must express one edge through the selected entry recipe"
                        )
                    if setup_mode is not None and variant.entry.params.get("setup_mode") != setup_mode:
                        raise ValueError(
                            "all five certified-recipe variants must use the selected frozen trend mechanic"
                        )
            elif self.authoring_lane == "visual_completed_bar_rule":
                if self.certified_recipe is not None:
                    raise ValueError("visual-rule campaigns cannot also declare a certified recipe")
                if any(variant.entry.module != "safe_bar_rule" for variant in self.variants):
                    raise ValueError("all five visual-rule variants must use the same reviewed safe_bar_rule edge")
            if not all(variant.confirmed for variant in self.variants):
                raise ValueError("a frozen campaign requires all five variants to be explicitly confirmed")
            expected = campaign_confirmation_context_sha256(self)
            if self.confirmation_context_sha256 != expected:
                raise ValueError(
                    "variant confirmations are stale for the current brief, data, execution, or mechanics context"
                )
        return self


def campaign_confirmation_context_sha256(
    value: CampaignDraftV1 | Mapping[str, Any],
) -> str:
    """Hash every reviewed pre-PnL input while excluding mutable UI flags."""

    if isinstance(value, CampaignDraftV1):
        parsed = value
    else:
        candidate = dict(value)
        candidate["frozen"] = False
        candidate["confirmation_context_sha256"] = None
        parsed = CampaignDraftV1.model_validate(candidate)
    payload = parsed.model_dump(
        mode="json",
        by_alias=True,
        exclude={"frozen", "confirmation_context_sha256"},
    )
    for variant in payload.get("variants") or []:
        variant.pop("confirmed", None)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _condition_tunable_names(condition: ConditionV1 | None) -> set[str]:
    if condition is None:
        return set()
    if isinstance(condition, (AllConditionV1, AnyConditionV1)):
        return set().union(*(_condition_tunable_names(item) for item in condition.conditions))
    if isinstance(condition, NotConditionV1):
        return _condition_tunable_names(condition.condition)
    expressions: list[ValueExpressionV1]
    if isinstance(condition, ComparisonConditionV1):
        expressions = [condition.left, condition.right]
    elif isinstance(condition, RangeConditionV1):
        expressions = [condition.value, condition.lower, condition.upper]
    else:
        expressions = [condition.left, condition.right]
    return {item.name for item in expressions if isinstance(item, TunableValueV1)}


def _canonical_scalar(value: Scalar) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _matches_value_type(value: Scalar, value_type: str) -> bool:
    if value_type == "boolean":
        return type(value) is bool
    if value_type == "integer":
        return type(value) is int
    if value_type == "number":
        return type(value) in {int, float} and not isinstance(value, bool)
    if value_type == "string":
        return type(value) is str
    return False


def _binding_structure(binding: ModuleBindingV1, module_type: str) -> dict[str, Any]:
    structure: dict[str, Any] = {"module": binding.module, "module_type": module_type}
    if binding.module == "safe_bar_rule" and isinstance(binding.params.get("rule"), dict):
        structure["rule"] = _strip_rule_values(binding.params["rule"])
    elif binding.module == "daily_time_series_momentum":
        structure["setup_mode"] = binding.params.get("setup_mode", "close_to_close_trend")
    return structure


def _strip_rule_values(value: Any) -> Any:
    if isinstance(value, list):
        return [_strip_rule_values(item) for item in value]
    if not isinstance(value, dict):
        return "<value>"
    source = value.get("source")
    if source == "constant":
        return {"source": "constant", "value_type": type(value.get("value")).__name__}
    if source == "tunable":
        return {"source": "tunable"}
    ignored = {"values", "default", "signal_start_time", "signal_end_time", "bar_interval_minutes"}
    return {key: _strip_rule_values(item) for key, item in sorted(value.items()) if key not in ignored}


AllConditionV1.model_rebuild()
AnyConditionV1.model_rebuild()
NotConditionV1.model_rebuild()
BarRuleV1.model_rebuild()


__all__ = [
    "AllConditionV1",
    "AnyConditionV1",
    "BUILTIN_BAR_FEATURES",
    "CERTIFIED_RECIPE_BINDINGS",
    "BarRuleV1",
    "CampaignDraftV1",
    "ComparisonConditionV1",
    "ConditionV1",
    "ConstantValueV1",
    "CrossConditionV1",
    "DatasetManifestV1",
    "DuplicateReviewV1",
    "EconomicEdgeFingerprintV1",
    "ExecutionSettingsV1",
    "FeatureValueV1",
    "ModuleBindingV1",
    "ModuleManifestV1",
    "NotConditionV1",
    "ParameterSpecV1",
    "RangeConditionV1",
    "ResearchSourceV1",
    "RollingValueV1",
    "TunableDefinitionV1",
    "TunableValueV1",
    "ValueExpressionV1",
    "VariantDraftV1",
    "campaign_confirmation_context_sha256",
]
