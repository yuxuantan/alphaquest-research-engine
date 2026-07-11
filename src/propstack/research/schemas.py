from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class SchemaValidationError(ValueError):
    """Raised when a config or generated artifact violates the engine contract."""


REQUIRED_CONFIG_KEYS = (
    "campaign_id",
    "variant_id",
    "timeframe",
    "data",
    "strategy",
    "core",
)
REQUIRED_STRATEGY_KEYS = ("entry", "tp", "sl")
REQUIRED_STAGE_RESULT_KEYS = ("stage", "label", "status", "passed", "criteria")
REQUIRED_RUN_SUMMARY_KEYS = (
    "campaign_id",
    "variant_id",
    "test_run_id",
    "symbol",
    "dataset_id",
    "timeframe",
    "config_hash",
    "source_config_hash",
    "output_dir",
    "created_at",
    "updated_at",
    "passed",
    "halted",
    "stages",
    "research_policy",
    "engine_contract_version",
)
VALID_STAGE_STATUSES = {"passed", "failed", "skipped", "error"}


def validate_campaign_config_contract(config: dict[str, Any], *, context: str = "config") -> None:
    _require_mapping(config, context)
    _require_keys(config, REQUIRED_CONFIG_KEYS, context)
    _require_mapping(config.get("data"), f"{context}.data")
    _require_mapping(config.get("strategy"), f"{context}.strategy")
    _require_mapping(config.get("core"), f"{context}.core")
    _require_config_or_data_value(config, "symbol", context)
    _require_config_or_data_value(config, "dataset_id", context)

    strategy = config["strategy"]
    _require_keys(strategy, REQUIRED_STRATEGY_KEYS, f"{context}.strategy")
    for section in REQUIRED_STRATEGY_KEYS:
        _require_mapping(strategy.get(section), f"{context}.strategy.{section}")
        _require_keys(strategy[section], ("module", "params"), f"{context}.strategy.{section}")
        _require_mapping(strategy[section].get("params"), f"{context}.strategy.{section}.params")


def validate_stage_result_contract(result: dict[str, Any], *, context: str = "stage_result") -> None:
    _require_mapping(result, context)
    _require_keys(result, REQUIRED_STAGE_RESULT_KEYS, context)
    status = result.get("status")
    if status not in VALID_STAGE_STATUSES:
        raise SchemaValidationError(f"{context}.status must be one of {sorted(VALID_STAGE_STATUSES)}; got {status!r}.")
    if not isinstance(result.get("passed"), bool):
        raise SchemaValidationError(f"{context}.passed must be boolean.")
    if not isinstance(result.get("criteria"), list):
        raise SchemaValidationError(f"{context}.criteria must be a list.")
    for index, item in enumerate(result.get("criteria") or [], start=1):
        _require_mapping(item, f"{context}.criteria[{index}]")
        _require_keys(item, ("metric", "passed"), f"{context}.criteria[{index}]")
        if not isinstance(item.get("passed"), bool):
            raise SchemaValidationError(f"{context}.criteria[{index}].passed must be boolean.")


def validate_run_summary_contract(summary: dict[str, Any], *, context: str = "campaign_test_summary") -> None:
    _require_mapping(summary, context)
    _require_keys(summary, REQUIRED_RUN_SUMMARY_KEYS, context)
    if not isinstance(summary.get("passed"), bool):
        raise SchemaValidationError(f"{context}.passed must be boolean.")
    if not isinstance(summary.get("halted"), bool):
        raise SchemaValidationError(f"{context}.halted must be boolean.")
    stages = summary.get("stages")
    if not isinstance(stages, list):
        raise SchemaValidationError(f"{context}.stages must be a list.")
    for index, stage in enumerate(stages, start=1):
        validate_stage_result_contract(stage, context=f"{context}.stages[{index}]")
    policy = summary.get("research_policy")
    _require_mapping(policy, f"{context}.research_policy")
    _require_keys(policy, ("version", "hash", "stage_order"), f"{context}.research_policy")
    if not isinstance(policy.get("stage_order"), list) or not policy["stage_order"]:
        raise SchemaValidationError(f"{context}.research_policy.stage_order must be a non-empty list.")


def _require_mapping(value: object, context: str) -> None:
    if not isinstance(value, dict):
        raise SchemaValidationError(f"{context} must be a mapping.")


def _require_keys(container: dict[str, Any], keys: Iterable[str], context: str) -> None:
    missing = [key for key in keys if key not in container or container.get(key) in (None, "")]
    if missing:
        raise SchemaValidationError(f"{context} missing required key(s): {', '.join(missing)}.")


def _require_config_or_data_value(config: dict[str, Any], key: str, context: str) -> None:
    data = config.get("data") if isinstance(config.get("data"), dict) else {}
    if config.get(key) in (None, "") and data.get(key) in (None, ""):
        raise SchemaValidationError(f"{context} missing required key {key} at top level or under data.")
