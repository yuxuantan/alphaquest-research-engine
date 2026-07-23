"""Versioned, hash-bound certification for custom strategy implementations.

Certification is deliberately separate from strategy configuration.  A config
chooses mechanics and parameters; this module proves which reviewed Python
implementation is allowed to interpret that config.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
from itertools import product
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable

import yaml


CERTIFICATION_SCHEMA = "alphaquest.strategy-certification/v1"
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


class StrategyCertificationError(ValueError):
    """Raised when executable strategy code is not currently certified."""


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
) -> dict[str, StrategyCertification]:
    root = project_root_for_certifications(project_root)
    manifest_root = certification_manifest_root(root)
    result: dict[str, StrategyCertification] = {}
    for path in sorted(manifest_root.glob("*.yaml")):
        certification = _load_manifest(path)
        if certification.strategy_id in result:
            raise StrategyCertificationError(
                f"duplicate strategy certification for {certification.strategy_id!r}"
            )
        if require_current:
            require_current_certification(certification, root)
        result[certification.strategy_id] = certification
    return result


def get_strategy_certification(
    strategy_id: str,
    project_root: str | Path | None = None,
    *,
    require_current: bool = True,
) -> StrategyCertification:
    certifications = load_strategy_certifications(project_root, require_current=require_current)
    try:
        return certifications[strategy_id]
    except KeyError as exc:
        raise StrategyCertificationError(f"strategy {strategy_id!r} has no certification manifest") from exc


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
) -> StrategyCertification | None:
    if str(config.get("engine_lane") or "") != "canonical_event_replay":
        return None
    strategy = config.get("strategy") if isinstance(config.get("strategy"), dict) else {}
    event = strategy.get("event") if isinstance(strategy.get("event"), dict) else {}
    strategy_id = str(event.get("module") or config.get("strategy_name") or "")
    certification = get_strategy_certification(strategy_id, project_root, require_current=True)
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
    return certification


def certify_strategy(strategy_id: str, project_root: str | Path) -> StrategyCertification:
    """Run the declared tests, then bind the manifest to the tested source bytes."""

    root = project_root_for_certifications(project_root)
    certification = get_strategy_certification(strategy_id, root, require_current=False)
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
    return get_strategy_certification(strategy_id, root, require_current=True)


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
    "REQUIRED_TEST_CATEGORIES",
    "StrategyCertification",
    "CertifiedStrategyParameter",
    "StrategyCertificationError",
    "audit_strategy_certification",
    "certify_strategy",
    "compute_implementation_sha256",
    "get_strategy_certification",
    "load_strategy_certifications",
    "normalize_certified_event_params",
    "resolve_factory",
    "strategy_identity_for_config",
    "validate_certified_event_parameter_grid",
    "validate_certified_parameter_value",
]
