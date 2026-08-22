"""Hash-bound, inspection-only component attribution.

Attribution is deliberately outside the strategy-approval path.  A contract is
sealed before any PnL is observed, and every leave-one-out run is executed by a
caller-supplied generic backtest callback.  The callback must attest that it
used the exact data, window, costs, parameter grid, and engine contract named
by the sealed contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Callable, Iterable, Mapping


ATTRIBUTION_SCHEMA = "alphaquest.component-attribution-contract/v1"
ATTRIBUTION_RESULT_SCHEMA = "alphaquest.component-attribution-result/v1"
INSPECTION_CLASSIFICATION = "INSPECTION_ONLY"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_BINDING_PATH = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
_CATEGORIES = {"entry", "sl", "tp"}
_ABLATION_STATUSES = {"eligible", "fixed"}


class AttributionContractError(ValueError):
    """Raised when an attribution declaration is invalid or has drifted."""


class AttributionExecutionError(RuntimeError):
    """Raised when an attribution run cannot preserve its sealed inputs."""


@dataclass(frozen=True)
class CertifiedNeutralReplacement:
    """A reviewed neutral binding for one claimed strategy component."""

    binding: Mapping[str, Any]
    strategy_id: str
    implementation_version: str
    implementation_sha256: str
    certification_manifest_sha256: str
    approved_edge_fingerprint_sha256: str
    methodology_category: str
    neutrality_rationale: str
    certification_status: str = "certified"

    def __post_init__(self) -> None:
        if not isinstance(self.binding, Mapping) or not self.binding:
            raise AttributionContractError("A neutral replacement binding must be a non-empty mapping.")
        _canonical_json(self.binding, context="neutral replacement binding")
        for label, value in (
            ("strategy_id", self.strategy_id),
            ("implementation_version", self.implementation_version),
            ("neutrality_rationale", self.neutrality_rationale),
        ):
            if not isinstance(value, str) or not value.strip():
                raise AttributionContractError(f"Neutral replacement {label} must be substantive.")
        for label, value in (
            ("implementation_sha256", self.implementation_sha256),
            ("certification_manifest_sha256", self.certification_manifest_sha256),
            ("approved_edge_fingerprint_sha256", self.approved_edge_fingerprint_sha256),
        ):
            _require_sha256(value, f"neutral replacement {label}")
        if self.methodology_category not in _CATEGORIES:
            raise AttributionContractError(
                f"Neutral replacement methodology_category must be one of {sorted(_CATEGORIES)}."
            )
        if self.certification_status != "certified":
            raise AttributionContractError("Neutral replacements must have certification_status='certified'.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding": _canonical_copy(self.binding),
            "strategy_id": self.strategy_id,
            "implementation_version": self.implementation_version,
            "implementation_sha256": self.implementation_sha256,
            "certification_manifest_sha256": self.certification_manifest_sha256,
            "approved_edge_fingerprint_sha256": self.approved_edge_fingerprint_sha256,
            "methodology_category": self.methodology_category,
            "neutrality_rationale": self.neutrality_rationale,
            "certification_status": self.certification_status,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CertifiedNeutralReplacement":
        try:
            return cls(
                binding=value["binding"],
                strategy_id=str(value["strategy_id"]),
                implementation_version=str(value["implementation_version"]),
                implementation_sha256=str(value["implementation_sha256"]),
                certification_manifest_sha256=str(value["certification_manifest_sha256"]),
                approved_edge_fingerprint_sha256=str(value["approved_edge_fingerprint_sha256"]),
                methodology_category=str(value["methodology_category"]),
                neutrality_rationale=str(value["neutrality_rationale"]),
                certification_status=str(value.get("certification_status", "")),
            )
        except (KeyError, TypeError) as exc:
            raise AttributionContractError(f"Malformed neutral replacement: missing {exc}.") from exc


@dataclass(frozen=True)
class ClaimedComponent:
    """A component claimed by the strategy author before performance testing."""

    component_id: str
    claimed_mechanism: str
    methodology_category: str
    binding_path: str
    full_binding_sha256: str
    neutral_replacement: CertifiedNeutralReplacement
    ablation_status: str = "eligible"

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.component_id):
            raise AttributionContractError(f"Invalid attribution component_id {self.component_id!r}.")
        if not isinstance(self.claimed_mechanism, str) or not self.claimed_mechanism.strip():
            raise AttributionContractError(f"Component {self.component_id!r} needs a claimed mechanism.")
        if self.methodology_category not in _CATEGORIES:
            raise AttributionContractError(
                f"Component {self.component_id!r} methodology_category must be one of {sorted(_CATEGORIES)}."
            )
        if not _BINDING_PATH.fullmatch(self.binding_path):
            raise AttributionContractError(
                f"Component {self.component_id!r} binding_path must be a dotted mapping path."
            )
        _require_sha256(self.full_binding_sha256, f"component {self.component_id} full_binding_sha256")
        if self.ablation_status not in _ABLATION_STATUSES:
            raise AttributionContractError(
                f"Component {self.component_id!r} ablation_status must be one of {sorted(_ABLATION_STATUSES)}."
            )
        if self.neutral_replacement.methodology_category != self.methodology_category:
            raise AttributionContractError(
                f"Component {self.component_id!r} and its neutral replacement have different methodology categories."
            )
        if _sha256_json(self.neutral_replacement.binding) == self.full_binding_sha256:
            raise AttributionContractError(
                f"Component {self.component_id!r} neutral replacement is identical to the full binding."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "claimed_mechanism": self.claimed_mechanism,
            "methodology_category": self.methodology_category,
            "binding_path": self.binding_path,
            "full_binding_sha256": self.full_binding_sha256,
            "neutral_replacement": self.neutral_replacement.to_dict(),
            "ablation_status": self.ablation_status,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ClaimedComponent":
        try:
            replacement = value["neutral_replacement"]
            if not isinstance(replacement, Mapping):
                raise TypeError("neutral_replacement")
            return cls(
                component_id=str(value["component_id"]),
                claimed_mechanism=str(value["claimed_mechanism"]),
                methodology_category=str(value["methodology_category"]),
                binding_path=str(value["binding_path"]),
                full_binding_sha256=str(value["full_binding_sha256"]),
                neutral_replacement=CertifiedNeutralReplacement.from_dict(replacement),
                ablation_status=str(value.get("ablation_status", "")),
            )
        except (KeyError, TypeError) as exc:
            raise AttributionContractError(f"Malformed claimed component: missing {exc}.") from exc


@dataclass(frozen=True)
class ComponentAttributionContract:
    schema: str
    campaign_id: str
    variant_id: str
    attempt_id: str
    declared_at: str
    pnl_observed_at_declaration: bool
    economic_edge_fingerprint_sha256: str
    research_objectives_sha256: str
    full_config_sha256: str
    data_sha256: str
    evaluation_window_sha256: str
    execution_costs_sha256: str
    parameter_grid_sha256: str
    engine_contract_sha256: str
    components: tuple[ClaimedComponent, ...]
    contract_sha256: str

    def __post_init__(self) -> None:
        if self.schema != ATTRIBUTION_SCHEMA:
            raise AttributionContractError(f"Unsupported attribution schema {self.schema!r}.")
        for label, value in (
            ("campaign_id", self.campaign_id),
            ("variant_id", self.variant_id),
            ("attempt_id", self.attempt_id),
        ):
            if not _IDENTIFIER.fullmatch(value):
                raise AttributionContractError(f"Invalid attribution {label} {value!r}.")
        _require_aware_timestamp(self.declared_at, "declared_at")
        if not isinstance(self.pnl_observed_at_declaration, bool):
            raise AttributionContractError("pnl_observed_at_declaration must be boolean.")
        if self.pnl_observed_at_declaration:
            raise AttributionContractError("Attribution must be declared and sealed before any PnL is observed.")
        for label, value in (
            ("economic_edge_fingerprint_sha256", self.economic_edge_fingerprint_sha256),
            ("research_objectives_sha256", self.research_objectives_sha256),
            ("full_config_sha256", self.full_config_sha256),
            ("data_sha256", self.data_sha256),
            ("evaluation_window_sha256", self.evaluation_window_sha256),
            ("execution_costs_sha256", self.execution_costs_sha256),
            ("parameter_grid_sha256", self.parameter_grid_sha256),
            ("engine_contract_sha256", self.engine_contract_sha256),
        ):
            _require_sha256(value, label)
        if not self.components:
            raise AttributionContractError("Attribution contracts must predeclare at least one claimed component.")
        identifiers = [item.component_id for item in self.components]
        paths = [item.binding_path for item in self.components]
        if len(identifiers) != len(set(identifiers)):
            raise AttributionContractError("Attribution component_id values must be unique.")
        if len(paths) != len(set(paths)):
            raise AttributionContractError("Attribution binding_path values must be unique.")
        for component in self.components:
            if (
                component.neutral_replacement.approved_edge_fingerprint_sha256
                != self.economic_edge_fingerprint_sha256
            ):
                raise AttributionContractError(
                    f"Component {component.component_id!r} neutral replacement is approved for a different economic edge."
                )
        _require_sha256(self.contract_sha256, "contract_sha256")
        expected = _sha256_json(self.to_dict(include_hash=False))
        if self.contract_sha256 != expected:
            raise AttributionContractError(
                f"Attribution contract hash mismatch: expected {expected}, got {self.contract_sha256}."
            )

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        payload = {
            "schema": self.schema,
            "campaign_id": self.campaign_id,
            "variant_id": self.variant_id,
            "attempt_id": self.attempt_id,
            "declared_at": self.declared_at,
            "pnl_observed_at_declaration": self.pnl_observed_at_declaration,
            "economic_edge_fingerprint_sha256": self.economic_edge_fingerprint_sha256,
            "research_objectives_sha256": self.research_objectives_sha256,
            "full_config_sha256": self.full_config_sha256,
            "data_sha256": self.data_sha256,
            "evaluation_window_sha256": self.evaluation_window_sha256,
            "execution_costs_sha256": self.execution_costs_sha256,
            "parameter_grid_sha256": self.parameter_grid_sha256,
            "engine_contract_sha256": self.engine_contract_sha256,
            "components": [item.to_dict() for item in self.components],
        }
        if include_hash:
            payload["contract_sha256"] = self.contract_sha256
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ComponentAttributionContract":
        try:
            raw_components = value["components"]
            if not isinstance(raw_components, list):
                raise TypeError("components")
            return cls(
                schema=str(value["schema"]),
                campaign_id=str(value["campaign_id"]),
                variant_id=str(value["variant_id"]),
                attempt_id=str(value["attempt_id"]),
                declared_at=str(value["declared_at"]),
                pnl_observed_at_declaration=value["pnl_observed_at_declaration"],
                economic_edge_fingerprint_sha256=str(value["economic_edge_fingerprint_sha256"]),
                research_objectives_sha256=str(value["research_objectives_sha256"]),
                full_config_sha256=str(value["full_config_sha256"]),
                data_sha256=str(value["data_sha256"]),
                evaluation_window_sha256=str(value["evaluation_window_sha256"]),
                execution_costs_sha256=str(value["execution_costs_sha256"]),
                parameter_grid_sha256=str(value["parameter_grid_sha256"]),
                engine_contract_sha256=str(value["engine_contract_sha256"]),
                components=tuple(ClaimedComponent.from_dict(item) for item in raw_components),
                contract_sha256=str(value["contract_sha256"]),
            )
        except (KeyError, TypeError) as exc:
            raise AttributionContractError(f"Malformed attribution contract: missing {exc}.") from exc


def seal_component_attribution_contract(
    *,
    campaign_id: str,
    variant_id: str,
    attempt_id: str,
    declared_at: str,
    pnl_observed: bool,
    economic_edge_fingerprint_sha256: str,
    research_objectives_sha256: str,
    full_config_sha256: str,
    data_sha256: str,
    evaluation_window_sha256: str,
    execution_costs_sha256: str,
    parameter_grid_sha256: str,
    engine_contract_sha256: str,
    components: Iterable[ClaimedComponent],
) -> ComponentAttributionContract:
    """Create a self-verifying declaration; observed PnL makes sealing illegal."""

    component_tuple = tuple(components)
    payload = {
        "schema": ATTRIBUTION_SCHEMA,
        "campaign_id": campaign_id,
        "variant_id": variant_id,
        "attempt_id": attempt_id,
        "declared_at": declared_at,
        "pnl_observed_at_declaration": bool(pnl_observed),
        "economic_edge_fingerprint_sha256": economic_edge_fingerprint_sha256,
        "research_objectives_sha256": research_objectives_sha256,
        "full_config_sha256": full_config_sha256,
        "data_sha256": data_sha256,
        "evaluation_window_sha256": evaluation_window_sha256,
        "execution_costs_sha256": execution_costs_sha256,
        "parameter_grid_sha256": parameter_grid_sha256,
        "engine_contract_sha256": engine_contract_sha256,
        "components": [item.to_dict() for item in component_tuple],
    }
    return ComponentAttributionContract(
        components=component_tuple,
        contract_sha256=_sha256_json(payload),
        **{key: value for key, value in payload.items() if key != "components"},
    )


def write_component_attribution_contract(
    path: str | Path, contract: ComponentAttributionContract
) -> Path:
    """Create an immutable contract file, allowing only byte-equivalent retries."""

    target = Path(path)
    payload = json.dumps(contract.to_dict(), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("x", encoding="utf-8") as handle:
            handle.write(payload)
    except FileExistsError:
        existing = read_component_attribution_contract(target)
        if existing.contract_sha256 != contract.contract_sha256:
            raise AttributionContractError(
                f"Attribution contract already exists with different contents: {target}."
            )
    return target


def read_component_attribution_contract(path: str | Path) -> ComponentAttributionContract:
    target = Path(path)
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AttributionContractError(f"Could not read attribution contract {target}: {exc}.") from exc
    if not isinstance(value, Mapping):
        raise AttributionContractError(f"Attribution contract {target} must contain a JSON object.")
    return ComponentAttributionContract.from_dict(value)


@dataclass(frozen=True)
class AttributionRunSpec:
    """The complete, immutable request passed to the generic backtest callback."""

    run_role: str
    component_id: str | None
    config: Mapping[str, Any]
    config_sha256: str
    data_sha256: str
    evaluation_window_sha256: str
    execution_costs_sha256: str
    parameter_grid_sha256: str
    engine_contract_sha256: str


@dataclass(frozen=True)
class AttributionBacktestResult:
    """Callback attestation returned with metrics for a single attribution run."""

    metrics: Mapping[str, float | int]
    config_sha256: str
    data_sha256: str
    evaluation_window_sha256: str
    execution_costs_sha256: str
    parameter_grid_sha256: str
    engine_contract_sha256: str


AttributionBacktest = Callable[[AttributionRunSpec], AttributionBacktestResult | Mapping[str, Any]]


def execute_component_attribution(
    contract: ComponentAttributionContract,
    full_config: Mapping[str, Any],
    backtest: AttributionBacktest,
    *,
    component_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Run full and leave-one-out configurations without granting approval.

    Positive deltas mean the full configuration produced a larger raw metric
    value than the neutral-replacement configuration.  Metric desirability is
    intentionally not inferred here (for example, lower drawdown is better).
    """

    # Re-parsing catches mutation of nested mappings held by a frozen dataclass.
    verified = ComponentAttributionContract.from_dict(contract.to_dict())
    if not isinstance(full_config, Mapping):
        raise AttributionExecutionError("The full attribution config must be a mapping.")
    actual_full_hash = _sha256_json(full_config)
    if actual_full_hash != verified.full_config_sha256:
        raise AttributionExecutionError(
            f"Full config hash drift: expected {verified.full_config_sha256}, got {actual_full_hash}."
        )

    by_id = {item.component_id: item for item in verified.components}
    requested = (
        [item.component_id for item in verified.components if item.ablation_status == "eligible"]
        if component_ids is None
        else list(component_ids)
    )
    if not requested:
        raise AttributionExecutionError("No eligible components were selected for attribution.")
    if len(requested) != len(set(requested)):
        raise AttributionExecutionError("A component may be ablated only once per attribution execution.")
    selected: list[ClaimedComponent] = []
    for component_id in requested:
        component = by_id.get(component_id)
        if component is None:
            raise AttributionExecutionError(
                f"Component {component_id!r} was not predeclared in the sealed attribution contract."
            )
        if component.ablation_status != "eligible":
            raise AttributionExecutionError(f"Component {component_id!r} is fixed and cannot be ablated.")
        if (
            component.neutral_replacement.approved_edge_fingerprint_sha256
            != verified.economic_edge_fingerprint_sha256
        ):
            raise AttributionExecutionError(
                f"Component {component_id!r} neutral replacement is approved for another economic edge."
            )
        selected.append(component)

    full_spec = _run_spec(verified, "full", None, full_config)
    full_result = _call_and_validate(backtest, full_spec)
    metric_names = set(full_result.metrics)
    rows: list[dict[str, Any]] = []
    for component in selected:
        ablated = _canonical_copy(full_config)
        full_binding = _binding_at_path(ablated, component.binding_path)
        binding_hash = _sha256_json(full_binding)
        if binding_hash != component.full_binding_sha256:
            raise AttributionExecutionError(
                f"Component {component.component_id!r} binding drift: expected "
                f"{component.full_binding_sha256}, got {binding_hash}."
            )
        _replace_binding(ablated, component.binding_path, component.neutral_replacement.binding)
        ablated_spec = _run_spec(verified, "leave_one_out", component.component_id, ablated)
        ablated_result = _call_and_validate(backtest, ablated_spec)
        if set(ablated_result.metrics) != metric_names:
            raise AttributionExecutionError(
                f"Component {component.component_id!r} returned a different metric schema from the full run."
            )
        delta = {
            name: float(full_result.metrics[name]) - float(ablated_result.metrics[name])
            for name in sorted(metric_names)
        }
        rows.append(
            {
                "component_id": component.component_id,
                "claimed_mechanism": component.claimed_mechanism,
                "methodology_category": component.methodology_category,
                "binding_path": component.binding_path,
                "neutral_strategy_id": component.neutral_replacement.strategy_id,
                "neutral_implementation_version": component.neutral_replacement.implementation_version,
                "neutral_binding_sha256": _sha256_json(component.neutral_replacement.binding),
                "leave_one_out_config_sha256": ablated_spec.config_sha256,
                "leave_one_out_metrics": _numeric_metrics(ablated_result.metrics),
                "delta_full_minus_leave_one_out": delta,
            }
        )

    payload = {
        "schema": ATTRIBUTION_RESULT_SCHEMA,
        "classification": INSPECTION_CLASSIFICATION,
        "approval_effect": "NONE",
        "promotion_authorized": False,
        "research_verdict": "NEEDS MANUAL REVIEW",
        "campaign_id": verified.campaign_id,
        "variant_id": verified.variant_id,
        "attempt_id": verified.attempt_id,
        "contract_sha256": verified.contract_sha256,
        "full_config_sha256": full_spec.config_sha256,
        "full_metrics": _numeric_metrics(full_result.metrics),
        "predeclared_components": [
            {
                "component_id": component.component_id,
                "binding_path": component.binding_path,
                "methodology_category": component.methodology_category,
                "ablation_status": component.ablation_status,
            }
            for component in verified.components
        ],
        "selected_component_ids": [component.component_id for component in selected],
        "component_deltas": rows,
        "interpretation": (
            "Inspection only. Raw leave-one-out deltas do not approve mechanics, performance, "
            "a candidate strategy, or deployment."
        ),
    }
    payload["result_sha256"] = _sha256_json(payload)
    return payload


def _run_spec(
    contract: ComponentAttributionContract,
    role: str,
    component_id: str | None,
    config: Mapping[str, Any],
) -> AttributionRunSpec:
    frozen_config = _canonical_copy(config)
    return AttributionRunSpec(
        run_role=role,
        component_id=component_id,
        config=frozen_config,
        config_sha256=_sha256_json(frozen_config),
        data_sha256=contract.data_sha256,
        evaluation_window_sha256=contract.evaluation_window_sha256,
        execution_costs_sha256=contract.execution_costs_sha256,
        parameter_grid_sha256=contract.parameter_grid_sha256,
        engine_contract_sha256=contract.engine_contract_sha256,
    )


def _call_and_validate(backtest: AttributionBacktest, spec: AttributionRunSpec) -> AttributionBacktestResult:
    try:
        raw = backtest(spec)
    except Exception as exc:  # callback failures must not become partial attribution evidence
        raise AttributionExecutionError(
            f"Generic backtest callback failed for {spec.run_role}/{spec.component_id or 'full'}: {exc}."
        ) from exc
    result = _coerce_result(raw)
    expected = {
        "config_sha256": spec.config_sha256,
        "data_sha256": spec.data_sha256,
        "evaluation_window_sha256": spec.evaluation_window_sha256,
        "execution_costs_sha256": spec.execution_costs_sha256,
        "parameter_grid_sha256": spec.parameter_grid_sha256,
        "engine_contract_sha256": spec.engine_contract_sha256,
    }
    if _sha256_json(spec.config) != spec.config_sha256:
        raise AttributionExecutionError("The generic backtest callback mutated its attribution config.")
    for field, expected_value in expected.items():
        actual = getattr(result, field)
        if actual != expected_value:
            raise AttributionExecutionError(
                f"Attribution {field} mismatch for {spec.run_role}/{spec.component_id or 'full'}: "
                f"expected {expected_value}, got {actual}."
            )
    _numeric_metrics(result.metrics)
    return result


def _coerce_result(value: AttributionBacktestResult | Mapping[str, Any]) -> AttributionBacktestResult:
    if isinstance(value, AttributionBacktestResult):
        return value
    if not isinstance(value, Mapping):
        raise AttributionExecutionError("Generic backtest callback must return AttributionBacktestResult or a mapping.")
    try:
        return AttributionBacktestResult(
            metrics=value["metrics"],
            config_sha256=str(value["config_sha256"]),
            data_sha256=str(value["data_sha256"]),
            evaluation_window_sha256=str(value["evaluation_window_sha256"]),
            execution_costs_sha256=str(value["execution_costs_sha256"]),
            parameter_grid_sha256=str(value["parameter_grid_sha256"]),
            engine_contract_sha256=str(value["engine_contract_sha256"]),
        )
    except (KeyError, TypeError) as exc:
        raise AttributionExecutionError(f"Malformed generic backtest result: missing {exc}.") from exc


def _numeric_metrics(value: Mapping[str, float | int]) -> dict[str, float]:
    if not isinstance(value, Mapping) or not value:
        raise AttributionExecutionError("Attribution backtests must return at least one numeric metric.")
    metrics: dict[str, float] = {}
    for name, raw in value.items():
        if not isinstance(name, str) or not name:
            raise AttributionExecutionError("Attribution metric names must be non-empty strings.")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(float(raw)):
            raise AttributionExecutionError(f"Attribution metric {name!r} must be finite and numeric.")
        metrics[name] = float(raw)
    return dict(sorted(metrics.items()))


def _binding_at_path(config: Mapping[str, Any], path: str) -> Any:
    current: Any = config
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise AttributionExecutionError(f"Declared attribution binding path {path!r} does not exist.")
        current = current[part]
    return current


def _replace_binding(config: dict[str, Any], path: str, replacement: Mapping[str, Any]) -> None:
    parts = path.split(".")
    current: Any = config
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            raise AttributionExecutionError(f"Declared attribution binding path {path!r} does not exist.")
        current = current[part]
    if not isinstance(current, dict) or parts[-1] not in current:
        raise AttributionExecutionError(f"Declared attribution binding path {path!r} does not exist.")
    current[parts[-1]] = _canonical_copy(replacement)


def _canonical_copy(value: Any) -> Any:
    return json.loads(_canonical_json(value, context="attribution value"))


def _canonical_json(value: Any, *, context: str) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise AttributionContractError(f"{context} must be canonical JSON: {exc}.") from exc


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value, context="hash input").encode("utf-8")).hexdigest()


def canonical_attribution_sha256(value: Any) -> str:
    """Return the strict canonical hash used by attribution declarations."""

    return _sha256_json(value)


def _require_sha256(value: str, label: str) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise AttributionContractError(f"{label} must be a lowercase SHA-256 hex digest.")


def _require_aware_timestamp(value: str, label: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise AttributionContractError(f"{label} must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AttributionContractError(f"{label} must include an explicit timezone offset.")


__all__ = [
    "ATTRIBUTION_RESULT_SCHEMA",
    "ATTRIBUTION_SCHEMA",
    "INSPECTION_CLASSIFICATION",
    "AttributionBacktestResult",
    "AttributionContractError",
    "AttributionExecutionError",
    "AttributionRunSpec",
    "CertifiedNeutralReplacement",
    "ClaimedComponent",
    "ComponentAttributionContract",
    "canonical_attribution_sha256",
    "execute_component_attribution",
    "read_component_attribution_contract",
    "seal_component_attribution_contract",
    "write_component_attribution_contract",
]
