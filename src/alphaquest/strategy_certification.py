"""Versioned, hash-bound certification for custom strategy implementations.

Certification is deliberately separate from strategy configuration.  A config
chooses mechanics and parameters; this module proves which reviewed Python
implementation is allowed to interpret that config.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from enum import Enum
import hashlib
import importlib
from itertools import product
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Mapping

import yaml


CERTIFICATION_SCHEMA = "alphaquest.strategy-certification/v1"
CERTIFIED_EXECUTION_CONTRACT_SCHEMA = "alphaquest.certified-execution-contract/v1"
STRATEGY_PACKAGE_AVAILABILITY_SCHEMA = "alphaquest.strategy-package-availability/v2"
LEGACY_STRATEGY_PACKAGE_AVAILABILITY_SCHEMA = "alphaquest.strategy-package-availability/v1"
REQUIRED_TEST_CATEGORIES = frozenset(
    {
        "session_logic",
        "entry_timing",
        "stop_target_ordering",
        "forced_flatten",
        "no_lookahead",
        "registry_and_runner",
    }
)
CERTIFIED_EXECUTION_DEFAULT_FIELDS = frozenset(
    {
        "timeframe",
        "entry_start",
        "latest_entry_time",
        "flatten_time",
        "max_trades_per_day",
        "daily_loss_limit",
        "daily_profit_stop",
        "commission_per_contract",
        "point_value",
        "tick_value",
        "execution_instrument",
        "signal_instrument",
        "executable_start_date",
        "slippage_ticks",
        "entry_slippage_ticks",
        "protective_stop_slippage_ticks",
        "target_limit_slippage_ticks",
        "market_exit_slippage_ticks",
        "event_stop_market_fill_policy",
        "contracts",
        "position_sizing",
        "prop_max_contracts",
        "monte_carlo_position_sizing",
    }
)


class StrategyCertificationError(ValueError):
    """Raised when executable strategy code is not currently certified."""


class StrategyPackageLifecycle(str, Enum):
    """Repository lifecycle state, independent of certification currentness."""

    DEVELOPMENT = "development"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"
    QUARANTINED = "quarantined"


class StrategyPackageAccess(str, Enum):
    """The action for which a package manifest is being requested."""

    NEW_WORK = "new_work"
    ENGINEERING = "engineering"
    HISTORICAL_REPLAY = "historical_replay"
    INSPECTION = "inspection"


_LIFECYCLES_BY_ACCESS = {
    StrategyPackageAccess.NEW_WORK: frozenset({StrategyPackageLifecycle.ACTIVE}),
    StrategyPackageAccess.ENGINEERING: frozenset(
        {
            StrategyPackageLifecycle.DEVELOPMENT,
            StrategyPackageLifecycle.ACTIVE,
            StrategyPackageLifecycle.DEPRECATED,
        }
    ),
    StrategyPackageAccess.HISTORICAL_REPLAY: frozenset(
        {StrategyPackageLifecycle.ACTIVE, StrategyPackageLifecycle.DEPRECATED}
    ),
    StrategyPackageAccess.INSPECTION: frozenset(StrategyPackageLifecycle),
}


@dataclass(frozen=True)
class StrategyPackageLifecycleRecord:
    """One package's repository-owned availability classification."""

    strategy_id: str
    lifecycle: StrategyPackageLifecycle
    lifecycle_changed_at: str
    reason: str

    def allows(self, access: StrategyPackageAccess | str) -> bool:
        return self.lifecycle in _LIFECYCLES_BY_ACCESS[StrategyPackageAccess(access)]


@dataclass(frozen=True)
class StrategyPackageAvailabilityPolicy:
    """Repository-owned strategy-package lifecycle classification."""

    policy_version: str
    packages: dict[str, StrategyPackageLifecycleRecord]
    historical_evidence_policy: str
    path: Path

    def ids_for(self, lifecycle: StrategyPackageLifecycle | str) -> frozenset[str]:
        expected = StrategyPackageLifecycle(lifecycle)
        return frozenset(
            strategy_id
            for strategy_id, record in self.packages.items()
            if record.lifecycle is expected
        )

    def ids_allowed_for(self, access: StrategyPackageAccess | str) -> frozenset[str]:
        requested = StrategyPackageAccess(access)
        return frozenset(
            strategy_id
            for strategy_id, record in self.packages.items()
            if record.allows(requested)
        )

    def lifecycle_for(self, strategy_id: str) -> StrategyPackageLifecycle:
        try:
            return self.packages[strategy_id].lifecycle
        except KeyError as exc:
            raise StrategyCertificationError(
                f"strategy package {strategy_id!r} is not classified by the lifecycle policy"
            ) from exc

    def allows(self, strategy_id: str, access: StrategyPackageAccess | str) -> bool:
        record = self.packages.get(strategy_id)
        return record is not None and record.allows(access)

    @property
    def active_strategy_ids(self) -> frozenset[str]:
        """Compatibility projection used by existing authoring/catalog callers."""

        return self.ids_for(StrategyPackageLifecycle.ACTIVE)

    @property
    def development_strategy_ids(self) -> frozenset[str]:
        return self.ids_for(StrategyPackageLifecycle.DEVELOPMENT)

    @property
    def deprecated_strategy_ids(self) -> frozenset[str]:
        return self.ids_for(StrategyPackageLifecycle.DEPRECATED)

    @property
    def retired_strategy_ids(self) -> frozenset[str]:
        return self.ids_for(StrategyPackageLifecycle.RETIRED)

    @property
    def quarantined_strategy_ids(self) -> frozenset[str]:
        return self.ids_for(StrategyPackageLifecycle.QUARANTINED)


def load_strategy_package_availability(
    project_root: str | Path | None = None,
) -> StrategyPackageAvailabilityPolicy:
    """Load the execution/publication allowlist and fail closed on ambiguity."""

    root = project_root_for_certifications(project_root)
    path = root / "config" / "strategy_packages.yaml"
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise StrategyCertificationError(
            f"strategy package availability policy is unavailable: {exc}"
        ) from exc
    if not isinstance(document, dict) or document.get("schema") not in {
        STRATEGY_PACKAGE_AVAILABILITY_SCHEMA,
        LEGACY_STRATEGY_PACKAGE_AVAILABILITY_SCHEMA,
    }:
        raise StrategyCertificationError(
            f"unsupported strategy package availability policy in {path}"
        )
    if document.get("schema") == LEGACY_STRATEGY_PACKAGE_AVAILABILITY_SCHEMA:
        packages = _load_legacy_strategy_package_records(document)
    else:
        packages = _load_strategy_package_records(document)
    if not packages:
        raise StrategyCertificationError("strategy_packages must classify at least one package")
    if not any(
        record.lifecycle is StrategyPackageLifecycle.ACTIVE
        for record in packages.values()
    ):
        raise StrategyCertificationError("strategy package policy must declare at least one active package")
    historical_policy = str(document.get("historical_evidence_policy") or "")
    if historical_policy != "preserve_read_only":
        raise StrategyCertificationError(
            "historical_evidence_policy must be preserve_read_only"
        )
    policy_version = document.get("policy_version")
    if not isinstance(policy_version, str) or not policy_version.strip():
        raise StrategyCertificationError(
            "strategy package policy_version must be a non-empty string"
        )
    return StrategyPackageAvailabilityPolicy(
        policy_version=policy_version.strip(),
        packages=packages,
        historical_evidence_policy=historical_policy,
        path=path.resolve(),
    )


def _load_strategy_package_records(
    document: dict[str, Any],
) -> dict[str, StrategyPackageLifecycleRecord]:
    raw_packages = document.get("strategy_packages")
    if not isinstance(raw_packages, dict):
        raise StrategyCertificationError("strategy_packages must be a mapping")
    records: dict[str, StrategyPackageLifecycleRecord] = {}
    for raw_strategy_id, raw_record in raw_packages.items():
        if not isinstance(raw_strategy_id, str) or not raw_strategy_id.strip():
            raise StrategyCertificationError("strategy_packages keys must be non-empty strings")
        strategy_id = raw_strategy_id.strip()
        if strategy_id in records:
            raise StrategyCertificationError(f"duplicate strategy package {strategy_id!r}")
        if not isinstance(raw_record, dict):
            raise StrategyCertificationError(
                f"lifecycle record for {strategy_id!r} must be a mapping"
            )
        try:
            lifecycle = StrategyPackageLifecycle(str(raw_record.get("lifecycle") or ""))
        except ValueError as exc:
            allowed = ", ".join(item.value for item in StrategyPackageLifecycle)
            raise StrategyCertificationError(
                f"lifecycle record for {strategy_id!r} must use one of: {allowed}"
            ) from exc
        changed_at = raw_record.get("lifecycle_changed_at")
        reason = raw_record.get("reason")
        if not isinstance(changed_at, str) or not changed_at.strip():
            raise StrategyCertificationError(
                f"lifecycle record for {strategy_id!r} requires string lifecycle_changed_at"
            )
        if not isinstance(reason, str) or not reason.strip():
            raise StrategyCertificationError(
                f"lifecycle record for {strategy_id!r} requires string reason"
            )
        records[strategy_id] = StrategyPackageLifecycleRecord(
            strategy_id=strategy_id,
            lifecycle=lifecycle,
            lifecycle_changed_at=changed_at.strip(),
            reason=reason.strip(),
        )
    return records


def _load_legacy_strategy_package_records(
    document: dict[str, Any],
) -> dict[str, StrategyPackageLifecycleRecord]:
    """Read the former active/retired policy without changing its meaning."""

    active = document.get("active_strategy_ids")
    retired = document.get("retired_strategy_ids")
    if not isinstance(active, list) or not active:
        raise StrategyCertificationError("active_strategy_ids must be a non-empty list")
    if not isinstance(retired, dict):
        raise StrategyCertificationError("retired_strategy_ids must be a mapping")
    if not all(isinstance(item, str) and item.strip() for item in active):
        raise StrategyCertificationError(
            "active_strategy_ids must contain only non-empty strings"
        )
    active_ids = [item.strip() for item in active]
    if len(set(active_ids)) != len(active_ids):
        raise StrategyCertificationError("active_strategy_ids must be unique and non-empty")
    overlap = sorted(set(active_ids) & {str(item).strip() for item in retired})
    if overlap:
        raise StrategyCertificationError(
            "strategy package IDs cannot be both active and retired: " + ", ".join(overlap)
        )
    records = {
        strategy_id: StrategyPackageLifecycleRecord(
            strategy_id=strategy_id,
            lifecycle=StrategyPackageLifecycle.ACTIVE,
            lifecycle_changed_at=str(document.get("policy_version") or "legacy"),
            reason="Imported from legacy active_strategy_ids policy.",
        )
        for strategy_id in active_ids
    }
    for raw_strategy_id, retirement in retired.items():
        if not isinstance(raw_strategy_id, str) or not raw_strategy_id.strip():
            raise StrategyCertificationError(
                "retired_strategy_ids keys must be non-empty strings"
            )
        strategy_id = raw_strategy_id.strip()
        if not isinstance(retirement, dict):
            raise StrategyCertificationError(
                f"retirement record for {strategy_id!r} must be a mapping"
            )
        retired_at = retirement.get("retired_at")
        reason = retirement.get("reason")
        if not isinstance(retired_at, str) or not retired_at.strip():
            raise StrategyCertificationError(
                f"retirement record for {strategy_id!r} requires string retired_at"
            )
        if not isinstance(reason, str) or not reason.strip():
            raise StrategyCertificationError(
                f"retirement record for {strategy_id!r} requires string reason"
            )
        records[strategy_id] = StrategyPackageLifecycleRecord(
            strategy_id=strategy_id,
            lifecycle=StrategyPackageLifecycle.RETIRED,
            lifecycle_changed_at=retired_at.strip(),
            reason=reason.strip(),
        )
    return records


@dataclass(frozen=True)
class CertifiedStrategyParameter:
    """One typed parameter accepted by a certified event strategy.

    ``category`` is the methodology budget bucket. ``tunable`` means a
    researcher may predeclare a grid for the parameter; it does not make the
    parameter tunable by default.
    """

    name: str
    category: str
    value_type: str
    default: Any
    description: str
    tunable: bool
    studio_editable: bool
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[Any, ...] = ()

    def public_record(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "value_type": self.value_type,
            "default": self.default,
            "description": self.description,
            "tunable": self.tunable,
            "studio_editable": self.studio_editable,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "choices": list(self.choices),
        }


@dataclass(frozen=True)
class StrategyCertification:
    strategy_id: str
    implementation_version: int
    certification_status: str
    lane: str
    factory: str
    entry_module: str
    stop_module: str
    target_module: str
    source_files: tuple[str, ...]
    implementation_sha256: str
    required_test_categories: tuple[str, ...]
    required_tests: tuple[str, ...]
    parameters: dict[str, CertifiedStrategyParameter]
    studio: dict[str, Any]
    manifest_path: Path
    manifest_sha256: str

    def public_record(self) -> dict[str, Any]:
        return {
            "schema": CERTIFICATION_SCHEMA,
            "strategy_id": self.strategy_id,
            "implementation_version": self.implementation_version,
            "certification_status": self.certification_status,
            "lane": self.lane,
            "entry_module": self.entry_module,
            "stop_module": self.stop_module,
            "target_module": self.target_module,
            "implementation_sha256": self.implementation_sha256,
            "manifest_sha256": self.manifest_sha256,
            "required_test_categories": list(self.required_test_categories),
            "required_tests": list(self.required_tests),
            "parameters": {
                name: parameter.public_record() for name, parameter in self.parameters.items()
            },
            "studio": dict(self.studio),
        }


def certified_execution_defaults(
    certification: StrategyCertification,
) -> dict[str, Any]:
    """Return and validate the manifest-owned executable contract.

    ``studio.execution_defaults`` was historically treated as optional UI
    metadata by fresh authoring while certification refreshes applied it to
    configs.  It is now one fixed, manifest-owned contract for every certified
    event config.  Campaign-owned values that are intentionally variable must
    therefore stay outside this mapping.
    """

    raw = certification.studio.get("execution_defaults")
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise StrategyCertificationError(
            "certified studio.execution_defaults must be a mapping"
        )
    unknown = sorted(set(raw) - CERTIFIED_EXECUTION_DEFAULT_FIELDS)
    if unknown:
        raise StrategyCertificationError(
            "unsupported certified execution default(s): " + ", ".join(unknown)
        )
    defaults = deepcopy(dict(raw))
    for name in ("position_sizing", "monte_carlo_position_sizing"):
        if name in defaults and not isinstance(defaults[name], Mapping):
            raise StrategyCertificationError(
                f"certified {name} must be a mapping"
            )
        if name in defaults:
            defaults[name] = deepcopy(dict(defaults[name]))
            _validate_certified_position_sizing(defaults[name], context=name)
    if "contracts" in defaults and int(defaults["contracts"]) < 1:
        raise StrategyCertificationError("certified contracts must be at least one")
    if "prop_max_contracts" in defaults and int(defaults["prop_max_contracts"]) < 1:
        raise StrategyCertificationError(
            "certified prop_max_contracts must be at least one"
        )
    if "executable_start_date" in defaults:
        try:
            date.fromisoformat(str(defaults["executable_start_date"]))
        except ValueError as exc:
            raise StrategyCertificationError(
                "certified executable_start_date must be an ISO date"
            ) from exc
    return defaults


def _validate_certified_position_sizing(
    sizing: Mapping[str, Any],
    *,
    context: str,
) -> None:
    mode = str(sizing.get("mode") or "")
    if mode not in {
        "fixed_contracts",
        "fixed_dollar_risk",
        "fixed_risk_budget",
        "risk_percent_net_liq",
        "risk_percent_initial_balance",
        "reference",
    }:
        raise StrategyCertificationError(
            f"certified {context}.mode is unsupported: {mode!r}"
        )
    if mode == "fixed_contracts" and int(sizing.get("contracts") or 0) < 1:
        raise StrategyCertificationError(
            f"certified {context}.contracts must be at least one"
        )
    if mode in {"fixed_dollar_risk", "fixed_risk_budget"}:
        risk_budget = sizing.get("risk_budget")
        if not isinstance(risk_budget, (int, float)) or float(risk_budget) <= 0:
            raise StrategyCertificationError(
                f"certified {context}.risk_budget must be positive"
            )
    if mode in {"risk_percent_net_liq", "risk_percent_initial_balance"}:
        risk_pct = sizing.get("risk_pct")
        if not isinstance(risk_pct, (int, float)) or not 0 < float(risk_pct) <= 1:
            raise StrategyCertificationError(
                f"certified {context}.risk_pct must be in (0, 1]"
            )
    if "min_contracts" in sizing and int(sizing["min_contracts"]) < 1:
        raise StrategyCertificationError(
            f"certified {context}.min_contracts must be at least one"
        )


def _execution_contract_record(
    certification: StrategyCertification,
    defaults: Mapping[str, Any],
) -> dict[str, Any]:
    canonical = json.dumps(
        dict(defaults),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return {
        "schema": CERTIFIED_EXECUTION_CONTRACT_SCHEMA,
        "strategy_id": certification.strategy_id,
        "manifest_sha256": certification.manifest_sha256,
        "execution_defaults_sha256": hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest(),
        "resolved_defaults": deepcopy(dict(defaults)),
    }


def apply_certified_execution_contract(
    config: dict[str, Any],
    certification: StrategyCertification,
    *,
    variant_id: str | None = None,
) -> list[dict[str, Any]]:
    """Apply the exact manifest execution contract and record every change."""

    defaults = certified_execution_defaults(certification)
    if not defaults:
        return []
    variant = str(variant_id or config.get("variant_id") or "")
    core = config.setdefault("core", {})
    if not isinstance(core, dict):
        raise StrategyCertificationError("core must be a mapping")
    changes: list[dict[str, Any]] = []

    def replace(scope: str, owner: dict[str, Any], name: str, value: Any) -> None:
        new_value = deepcopy(value)
        old_value = deepcopy(owner.get(name))
        owner[name] = new_value
        if old_value != new_value:
            changes.append(
                {
                    "variant_id": variant,
                    "scope": scope,
                    "field": name,
                    "old": old_value,
                    "new": deepcopy(new_value),
                    "reviewed": True,
                    "change_kind": "certified_execution_contract",
                }
            )

    for name, value in defaults.items():
        if name == "executable_start_date":
            start_date = date.fromisoformat(str(value))
            for section_name in ("core", "core_grid", "monkey", "wfa"):
                section = config.get(section_name)
                if not isinstance(section, dict):
                    continue
                subset = section.setdefault("data_subset", {})
                if not isinstance(subset, dict):
                    raise StrategyCertificationError(
                        f"{section_name}.data_subset must be a mapping"
                    )
                old_value = subset.get("start_date")
                if old_value is None or date.fromisoformat(str(old_value)) < start_date:
                    replace(
                        f"{section_name}.data_subset",
                        subset,
                        "start_date",
                        start_date.isoformat(),
                    )
            continue
        if name == "monte_carlo_position_sizing":
            monte_carlo = config.setdefault("monte_carlo", {})
            if not isinstance(monte_carlo, dict):
                raise StrategyCertificationError("monte_carlo must be a mapping")
            replace("monte_carlo", monte_carlo, "position_sizing", value)
            continue
        if name == "prop_max_contracts":
            prop_rules = config.setdefault("prop_rules", {})
            if not isinstance(prop_rules, dict):
                raise StrategyCertificationError("prop_rules must be a mapping")
            replace("prop_rules", prop_rules, "max_contracts", int(value))
            continue
        if name == "timeframe":
            replace("config", config, "timeframe", str(value))
            continue
        replace("core", core, name, value)

    flatten = defaults.get("flatten_time")
    if flatten is not None:
        strategy = config.setdefault("strategy", {})
        if not isinstance(strategy, dict):
            raise StrategyCertificationError("strategy must be a mapping")
        replace("strategy", strategy, "flatten_time", str(flatten))
    apex = config.setdefault("apex_rules", {})
    if not isinstance(apex, dict):
        raise StrategyCertificationError("apex_rules must be a mapping")
    for name, value in (
        ("latest_entry_time", defaults.get("latest_entry_time")),
        ("force_flatten_time", flatten),
        ("latest_flat_time", flatten),
    ):
        if value is not None:
            replace("apex_rules", apex, name, str(value))

    replace(
        "config",
        config,
        "certified_execution_contract",
        _execution_contract_record(certification, defaults),
    )
    return changes


def require_certified_execution_contract(
    config: Mapping[str, Any],
    certification: StrategyCertification,
) -> None:
    """Fail closed when a config differs from its manifest execution contract."""

    candidate = deepcopy(dict(config))
    changes = apply_certified_execution_contract(candidate, certification)
    if changes:
        mismatches = ", ".join(
            f"{change['scope']}.{change['field']}"
            for change in changes
        )
        raise StrategyCertificationError(
            "config certified execution contract is missing or mismatched: "
            + mismatches
        )


def validate_certified_parameter_value(
    parameter: CertifiedStrategyParameter,
    value: Any,
    *,
    context: str | None = None,
) -> None:
    """Fail closed when a default or grid value violates its certified type."""

    prefix = f"{context}: " if context else ""
    valid_type = {
        "boolean": type(value) is bool,
        "integer": type(value) is int,
        "number": type(value) in {int, float} and not isinstance(value, bool),
        "string": type(value) is str,
    }.get(parameter.value_type, False)
    if not valid_type:
        raise StrategyCertificationError(
            f"{prefix}{parameter.name} must be {parameter.value_type}, got {type(value).__name__}"
        )
    if isinstance(value, float) and not __import__("math").isfinite(value):
        raise StrategyCertificationError(f"{prefix}{parameter.name} must be finite")
    if parameter.minimum is not None and float(value) < parameter.minimum:
        raise StrategyCertificationError(
            f"{prefix}{parameter.name} must be at least {parameter.minimum}"
        )
    if parameter.maximum is not None and float(value) > parameter.maximum:
        raise StrategyCertificationError(
            f"{prefix}{parameter.name} must be at most {parameter.maximum}"
        )
    if parameter.choices and value not in parameter.choices:
        raise StrategyCertificationError(
            f"{prefix}{parameter.name} must be one of {list(parameter.choices)!r}"
        )


def normalize_certified_event_params(
    certification: StrategyCertification,
    params: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a complete, typed parameter mapping from certified defaults."""

    supplied = dict(params or {})
    unknown = sorted(set(supplied) - set(certification.parameters))
    if unknown:
        raise StrategyCertificationError(
            f"strategy {certification.strategy_id!r} has unknown parameter(s): {', '.join(unknown)}"
        )
    normalized: dict[str, Any] = {}
    for name, parameter in certification.parameters.items():
        value = supplied.get(name, parameter.default)
        validate_certified_parameter_value(parameter, value, context=certification.strategy_id)
        normalized[name] = value
    return normalized


def validate_certified_event_parameter_grid(
    certification: StrategyCertification,
    params: dict[str, Any],
    grid: dict[str, list[Any]] | None,
    *,
    qualified_keys: bool = False,
) -> dict[str, list[Any]]:
    """Validate and canonicalize a predeclared certified-event parameter grid."""

    normalized_params = normalize_certified_event_params(certification, params)
    supplied = dict(grid or {})
    canonical: dict[str, list[Any]] = {}
    counts = {"entry": 0, "sl": 0, "tp": 0}
    combinations = 1
    for supplied_name, raw_values in supplied.items():
        name = str(supplied_name)
        if qualified_keys:
            prefix = "event.params."
            if not name.startswith(prefix):
                raise StrategyCertificationError(
                    f"certified event grids may only use {prefix}<parameter> keys, got {name!r}"
                )
            name = name[len(prefix) :]
        parameter = certification.parameters.get(name)
        if parameter is None:
            raise StrategyCertificationError(f"unknown certified event tunable parameter {name!r}")
        if not parameter.tunable:
            raise StrategyCertificationError(f"certified event parameter {name!r} is fixed and cannot be tuned")
        if not isinstance(raw_values, list) or len(raw_values) < 2:
            raise StrategyCertificationError(
                f"certified event parameter grid {name!r} must contain at least two values"
            )
        values: list[Any] = []
        fingerprints: set[tuple[str, str]] = set()
        for value in raw_values:
            validate_certified_parameter_value(parameter, value, context="parameter grid")
            fingerprint = _certified_parameter_value_fingerprint(parameter, value)
            if fingerprint in fingerprints:
                raise StrategyCertificationError(f"parameter grid {name!r} contains duplicate values")
            fingerprints.add(fingerprint)
            values.append(value)
        default = normalized_params[name]
        default_fingerprint = _certified_parameter_value_fingerprint(parameter, default)
        if not any(
            _certified_parameter_value_fingerprint(parameter, value) == default_fingerprint
            for value in values
        ):
            raise StrategyCertificationError(
                f"parameter grid {name!r} must include its reviewed default {default!r}"
            )
        counts[parameter.category] += 1
        combinations *= len(values)
        canonical[f"event.params.{name}"] = values
    if counts["entry"] > 2 or counts["sl"] > 1 or counts["tp"] > 1:
        raise StrategyCertificationError(
            "certified event parameter grid exceeds methodology caps "
            f"(entry={counts['entry']}, sl={counts['sl']}, tp={counts['tp']})"
        )
    if combinations != 1 and not 8 <= combinations <= 120:
        raise StrategyCertificationError(
            "certified event parameter space must contain exactly one or between 8 and 120 combinations"
        )
    names = [key.removeprefix("event.params.") for key in canonical]
    factory = resolve_factory(certification.factory)
    for values in product(*(canonical[f"event.params.{name}"] for name in names)):
        candidate = dict(normalized_params)
        candidate.update(dict(zip(names, values)))
        try:
            factory(candidate)
        except (TypeError, ValueError) as exc:
            rendered = ", ".join(f"{name}={value!r}" for name, value in zip(names, values))
            raise StrategyCertificationError(
                f"certified event parameter combination is mechanically invalid ({rendered}): {exc}"
            ) from exc
    return canonical


def _certified_parameter_value_fingerprint(
    parameter: CertifiedStrategyParameter,
    value: Any,
) -> tuple[str, str]:
    if parameter.value_type == "number":
        return ("number", json.dumps(float(value)))
    return (parameter.value_type, json.dumps(value, sort_keys=True))


def certification_manifest_root(project_root: str | Path | None = None) -> Path:
    if project_root is not None:
        return Path(project_root).resolve() / "src" / "alphaquest" / "strategy_certifications"
    return Path(__file__).resolve().parent / "strategy_certifications"


def project_root_for_certifications(project_root: str | Path | None = None) -> Path:
    if project_root is not None:
        return Path(project_root).resolve()
    source = Path(__file__).resolve()
    for parent in source.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src" / "alphaquest").is_dir():
            return parent
    raise StrategyCertificationError("could not locate the project root for strategy certification")


def load_strategy_certifications(
    project_root: str | Path | None = None,
    *,
    require_current: bool = True,
    include_retired: bool = False,
    access: StrategyPackageAccess | str | None = None,
) -> dict[str, StrategyCertification]:
    """Load strategy packages allowed by the repository-owned availability policy.

    The default is the active-only new-work view. ``include_retired=True`` is
    retained as a compatibility alias for active plus historical (deprecated
    and retired) manifest inspection; it does not expose development or
    quarantined packages and does not grant execution authority. New callers
    should state an explicit ``access`` purpose.
    """

    root = project_root_for_certifications(project_root)
    manifest_root = certification_manifest_root(root)
    result: dict[str, StrategyCertification] = {}
    for path in sorted(manifest_root.glob("*.yaml")):
        certification = _load_manifest(path)
        if certification.strategy_id in result:
            raise StrategyCertificationError(
                f"duplicate strategy certification for {certification.strategy_id!r}"
            )
        result[certification.strategy_id] = certification

    policy = load_strategy_package_availability(root)
    manifest_ids = set(result)
    classified_ids = set(policy.packages)
    missing_manifests = sorted(classified_ids - manifest_ids)
    if missing_manifests:
        raise StrategyCertificationError(
            "strategy package availability policy references missing manifest(s): "
            + ", ".join(missing_manifests)
        )
    unclassified_manifests = sorted(manifest_ids - classified_ids)
    if unclassified_manifests:
        raise StrategyCertificationError(
            "strategy certification manifest(s) are not classified by the lifecycle policy: "
            + ", ".join(unclassified_manifests)
        )

    requested_access = _strategy_package_access(
        access=access,
        include_retired=include_retired,
    )
    selected_ids = (
        set(policy.active_strategy_ids)
        | set(policy.deprecated_strategy_ids)
        | set(policy.retired_strategy_ids)
        if include_retired and access is None
        else set(policy.ids_allowed_for(requested_access))
    )
    selected = {strategy_id: result[strategy_id] for strategy_id in sorted(selected_ids)}
    if require_current:
        for certification in selected.values():
            require_current_certification(certification, root)
    return selected


def get_strategy_certification(
    strategy_id: str,
    project_root: str | Path | None = None,
    *,
    require_current: bool = True,
    include_retired: bool = False,
    access: StrategyPackageAccess | str | None = None,
) -> StrategyCertification:
    root = project_root_for_certifications(project_root)
    policy = load_strategy_package_availability(root)
    requested_access = _strategy_package_access(
        access=access,
        include_retired=include_retired,
    )
    if strategy_id not in policy.packages:
        raise StrategyCertificationError(
            f"strategy {strategy_id!r} is not classified by the lifecycle policy"
        )
    if include_retired and access is None:
        access_allowed = policy.lifecycle_for(strategy_id) in {
            StrategyPackageLifecycle.ACTIVE,
            StrategyPackageLifecycle.DEPRECATED,
            StrategyPackageLifecycle.RETIRED,
        }
    else:
        access_allowed = policy.allows(strategy_id, requested_access)
    if not access_allowed:
        lifecycle = policy.lifecycle_for(strategy_id)
        if include_retired and access is None:
            raise StrategyCertificationError(
                f"strategy {strategy_id!r} is {lifecycle.value} and is not exposed by the "
                "legacy include_retired compatibility flag; request an explicit access purpose"
            )
        raise StrategyCertificationError(
            _lifecycle_access_error(strategy_id, lifecycle, requested_access)
        )
    certifications = load_strategy_certifications(
        root,
        require_current=False,
        access=StrategyPackageAccess.INSPECTION,
    )
    try:
        certification = certifications[strategy_id]
    except KeyError as exc:
        raise StrategyCertificationError(f"strategy {strategy_id!r} has no certification manifest") from exc
    if require_current:
        require_current_certification(certification, root)
    return certification


def _strategy_package_access(
    *,
    access: StrategyPackageAccess | str | None,
    include_retired: bool,
) -> StrategyPackageAccess:
    if access is None:
        return (
            StrategyPackageAccess.INSPECTION
            if include_retired
            else StrategyPackageAccess.NEW_WORK
        )
    try:
        requested = StrategyPackageAccess(access)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in StrategyPackageAccess)
        raise StrategyCertificationError(
            f"strategy package access must use one of: {allowed}"
        ) from exc
    if include_retired and requested is not StrategyPackageAccess.INSPECTION:
        raise StrategyCertificationError(
            "include_retired=True is compatible only with access='inspection'"
        )
    return requested


def _lifecycle_access_error(
    strategy_id: str,
    lifecycle: StrategyPackageLifecycle,
    access: StrategyPackageAccess,
) -> str:
    descriptions = {
        StrategyPackageLifecycle.DEVELOPMENT: (
            "is in development and available only for engineering and inspection"
        ),
        StrategyPackageLifecycle.ACTIVE: "is active but the requested action is not permitted",
        StrategyPackageLifecycle.DEPRECATED: (
            "is deprecated and unavailable for new work; only engineering maintenance, "
            "exact historical replay, replication, and inspection are permitted"
        ),
        StrategyPackageLifecycle.RETIRED: (
            "is retired and available only for historical inspection"
        ),
        StrategyPackageLifecycle.QUARANTINED: (
            "is quarantined and unavailable for execution or certification; inspection only"
        ),
    }
    return (
        f"strategy {strategy_id!r} {descriptions[lifecycle]} "
        f"(requested access: {access.value})"
    )


def require_current_certification(
    certification: StrategyCertification,
    project_root: str | Path | None = None,
) -> StrategyCertification:
    root = project_root_for_certifications(project_root)
    errors = audit_strategy_certification(certification, root)
    if errors:
        raise StrategyCertificationError(
            f"strategy {certification.strategy_id!r} is not certified for execution:\n- "
            + "\n- ".join(errors)
        )
    return certification


def audit_strategy_certification(
    certification: StrategyCertification,
    project_root: str | Path | None = None,
) -> list[str]:
    root = project_root_for_certifications(project_root)
    errors: list[str] = []
    if certification.certification_status != "certified":
        errors.append("certification_status must be certified")
    if certification.lane != "canonical_event_replay":
        errors.append("only canonical_event_replay custom strategies are currently supported")
    if certification.implementation_version < 1:
        errors.append("implementation_version must be at least 1")
    missing_categories = REQUIRED_TEST_CATEGORIES - set(certification.required_test_categories)
    if missing_categories:
        errors.append("required test categories are missing: " + ", ".join(sorted(missing_categories)))
    if not certification.required_tests:
        errors.append("required_tests must declare executable pytest node IDs or paths")
    if not certification.parameters:
        errors.append("parameters must declare the complete certified event configuration")
    for name, parameter in certification.parameters.items():
        if name != parameter.name:
            errors.append(f"parameter key {name!r} does not match its parsed name")
        if parameter.category not in {"entry", "sl", "tp"}:
            errors.append(f"parameter {name!r} has unsupported category {parameter.category!r}")
        try:
            validate_certified_parameter_value(parameter, parameter.default)
        except StrategyCertificationError as exc:
            errors.append(str(exc))
    try:
        certified_execution_defaults(certification)
    except StrategyCertificationError as exc:
        errors.append(str(exc))
    try:
        actual = compute_implementation_sha256(root, certification.source_files)
    except StrategyCertificationError as exc:
        errors.append(str(exc))
    else:
        if actual != certification.implementation_sha256:
            errors.append(
                "implementation hash has drifted; run the required tests and recertify "
                f"(declared {certification.implementation_sha256}, actual {actual})"
            )
    try:
        resolve_factory(certification.factory)
    except (AttributeError, ImportError, TypeError, ValueError) as exc:
        errors.append(f"factory cannot be imported: {exc}")
    return errors


def compute_implementation_sha256(project_root: str | Path, source_files: tuple[str, ...] | list[str]) -> str:
    root = Path(project_root).resolve()
    if not source_files:
        raise StrategyCertificationError("source_files must not be empty")
    digest = hashlib.sha256()
    for relative in sorted(set(str(item) for item in source_files)):
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise StrategyCertificationError(f"source file escapes project root: {relative}") from exc
        if not candidate.is_file():
            raise StrategyCertificationError(f"certified source file is missing: {relative}")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(candidate.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def resolve_factory(value: str) -> Callable[[dict[str, Any]], object]:
    module_name, separator, attribute = value.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError("factory must use package.module:callable syntax")
    factory = getattr(importlib.import_module(module_name), attribute)
    if not callable(factory):
        raise TypeError(f"{value!r} is not callable")
    return factory


def strategy_identity_for_config(
    config: dict[str, Any],
    project_root: str | Path | None = None,
    *,
    require_declared_match: bool = True,
    access: StrategyPackageAccess | str | None = None,
) -> StrategyCertification | None:
    if str(config.get("engine_lane") or "") != "canonical_event_replay":
        return None
    strategy = config.get("strategy") if isinstance(config.get("strategy"), dict) else {}
    event = strategy.get("event") if isinstance(strategy.get("event"), dict) else {}
    strategy_id = str(event.get("module") or config.get("strategy_name") or "")
    requested_access = access or strategy_package_access_for_config(config)
    certification = get_strategy_certification(
        strategy_id,
        project_root,
        require_current=True,
        access=requested_access,
    )
    declared = config.get("strategy_certification")
    if require_declared_match and declared is not None:
        if not isinstance(declared, dict):
            raise StrategyCertificationError("strategy_certification must be a mapping")
        expected = certification.public_record()
        checks = {
            "strategy_id": expected["strategy_id"],
            "implementation_version": expected["implementation_version"],
            "implementation_sha256": expected["implementation_sha256"],
            "manifest_sha256": expected["manifest_sha256"],
        }
        mismatched = [name for name, value in checks.items() if declared.get(name) != value]
        if mismatched:
            raise StrategyCertificationError(
                "config strategy certification is stale or mismatched: " + ", ".join(mismatched)
            )
    research = config.get("research_metadata")
    authored_config = (
        isinstance(research, dict)
        and research.get("authoring_contract") == "alphaquest.campaign-draft/v1"
    )
    if (
        require_declared_match
        and StrategyPackageAccess(requested_access) is StrategyPackageAccess.NEW_WORK
        and (
            authored_config
            or config.get("certified_execution_contract") is not None
        )
    ):
        require_certified_execution_contract(config, certification)
    return certification


def strategy_package_access_for_config(config: dict[str, Any]) -> StrategyPackageAccess:
    """Grant deprecated-package replay only to authored exact replications.

    Ordinary publications, corrections, data refreshes, methodology reruns,
    rescues, and parameter declarations all remain active-package-only.
    Follow-up lineage validation is responsible for proving that an authored
    replication is a hash-bound child of an immutable parent.
    """

    if (
        str(config.get("attempt_kind") or "") == "replication"
        and str(config.get("attempt_provenance") or "") == "authored"
    ):
        return StrategyPackageAccess.HISTORICAL_REPLAY
    return StrategyPackageAccess.NEW_WORK


def certify_strategy(strategy_id: str, project_root: str | Path) -> StrategyCertification:
    """Run the declared tests, then bind the manifest to the tested source bytes."""

    root = project_root_for_certifications(project_root)
    certification = get_strategy_certification(
        strategy_id,
        root,
        require_current=False,
        access=StrategyPackageAccess.ENGINEERING,
    )
    if not certification.required_tests:
        raise StrategyCertificationError("certification cannot proceed without required_tests")
    previous = certification.manifest_path.read_bytes()
    document = yaml.safe_load(certification.manifest_path.read_text(encoding="utf-8")) or {}
    document["implementation_sha256"] = compute_implementation_sha256(root, certification.source_files)
    document["certification_status"] = "certified"
    certification.manifest_path.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *certification.required_tests],
        cwd=root,
        check=False,
    )
    if completed.returncode != 0:
        certification.manifest_path.write_bytes(previous)
        raise StrategyCertificationError("required certification tests failed; manifest was restored")
    return get_strategy_certification(
        strategy_id,
        root,
        require_current=True,
        access=StrategyPackageAccess.ENGINEERING,
    )


def _load_manifest(path: Path) -> StrategyCertification:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise StrategyCertificationError(f"could not read strategy certification {path}: {exc}") from exc
    if not isinstance(document, dict) or document.get("schema") != CERTIFICATION_SCHEMA:
        raise StrategyCertificationError(f"unsupported strategy certification schema in {path}")
    required = (
        "strategy_id",
        "implementation_version",
        "certification_status",
        "lane",
        "factory",
        "entry_module",
        "stop_module",
        "target_module",
        "source_files",
        "implementation_sha256",
        "required_test_categories",
        "required_tests",
        "parameters",
    )
    missing = [name for name in required if document.get(name) in (None, "", [])]
    if missing:
        raise StrategyCertificationError(f"strategy certification is missing: {', '.join(missing)}")
    parameter_document = document.get("parameters")
    if not isinstance(parameter_document, dict):
        raise StrategyCertificationError("strategy certification parameters must be a mapping")
    parameters: dict[str, CertifiedStrategyParameter] = {}
    for name, value in parameter_document.items():
        if not isinstance(value, dict):
            raise StrategyCertificationError(f"strategy parameter {name!r} must be a mapping")
        missing_parameter = [
            field
            for field in ("category", "value_type", "default", "description", "tunable", "studio_editable")
            if field not in value
        ]
        if missing_parameter:
            raise StrategyCertificationError(
                f"strategy parameter {name!r} is missing: {', '.join(missing_parameter)}"
            )
        parameters[str(name)] = CertifiedStrategyParameter(
            name=str(name),
            category=str(value["category"]),
            value_type=str(value["value_type"]),
            default=value["default"],
            description=str(value["description"]),
            tunable=bool(value["tunable"]),
            studio_editable=bool(value["studio_editable"]),
            minimum=float(value["minimum"]) if value.get("minimum") is not None else None,
            maximum=float(value["maximum"]) if value.get("maximum") is not None else None,
            choices=tuple(value.get("choices") or ()),
        )
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return StrategyCertification(
        strategy_id=str(document["strategy_id"]),
        implementation_version=int(document["implementation_version"]),
        certification_status=str(document["certification_status"]),
        lane=str(document["lane"]),
        factory=str(document["factory"]),
        entry_module=str(document["entry_module"]),
        stop_module=str(document["stop_module"]),
        target_module=str(document["target_module"]),
        source_files=tuple(str(item) for item in document["source_files"]),
        implementation_sha256=str(document["implementation_sha256"]),
        required_test_categories=tuple(str(item) for item in document["required_test_categories"]),
        required_tests=tuple(str(item) for item in document["required_tests"]),
        parameters=parameters,
        studio=dict(document.get("studio") or {}),
        manifest_path=path.resolve(),
        manifest_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )


__all__ = [
    "CERTIFICATION_SCHEMA",
    "CERTIFIED_EXECUTION_CONTRACT_SCHEMA",
    "CERTIFIED_EXECUTION_DEFAULT_FIELDS",
    "REQUIRED_TEST_CATEGORIES",
    "STRATEGY_PACKAGE_AVAILABILITY_SCHEMA",
    "StrategyCertification",
    "CertifiedStrategyParameter",
    "StrategyCertificationError",
    "StrategyPackageAccess",
    "StrategyPackageAvailabilityPolicy",
    "StrategyPackageLifecycle",
    "StrategyPackageLifecycleRecord",
    "audit_strategy_certification",
    "apply_certified_execution_contract",
    "certified_execution_defaults",
    "certify_strategy",
    "compute_implementation_sha256",
    "get_strategy_certification",
    "load_strategy_package_availability",
    "load_strategy_certifications",
    "normalize_certified_event_params",
    "require_certified_execution_contract",
    "resolve_factory",
    "strategy_identity_for_config",
    "strategy_package_access_for_config",
    "validate_certified_event_parameter_grid",
    "validate_certified_parameter_value",
]
