from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Iterable

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from alphaquest.data.load import infer_data_source, load_raw_data  # noqa: E402
from alphaquest.strategy_modules.entry import ENTRY_MODULES, entry_module_metadata  # noqa: E402
from alphaquest.strategy_modules.sl import SL_MODULES  # noqa: E402
from alphaquest.strategy_modules.tp import TP_MODULES  # noqa: E402
from alphaquest.utils.target_rr import MIN_TARGET_R_MULTIPLE, target_rr_violations  # noqa: E402


ACTIVE_CONFIG_GLOBS = (
    "research/campaigns/active/**/variants/**/config.yaml",
    "research/campaigns/active/**/rescue_attempts/**/config.yaml",
    "campaigns/**/variants/**/config.yaml",
    "campaigns/**/rescue_attempts/**/config.yaml",
    "configs/campaigns/**/*.yaml",
)
GENERATED_RESULT_CONFIG_GLOBS = (
    "research/evidence/runs/**/effective_config.yaml",
    "research/evidence/runs/**/config.yaml",
    "backtest-campaigns/**/effective_config.yaml",
    "backtest-campaigns/**/config.yaml",
)
REQUIRED_TOP_LEVEL = ("campaign_id", "variant_id", "symbol", "dataset_id", "timeframe", "data", "strategy", "core")
REQUIRED_CORE_FIELDS = ("tick_size", "commission_per_contract", "slippage_ticks")
REQUIRED_APEX_FIELDS = ("latest_flat_time", "force_flatten_time", "latest_entry_time")
REQUIRED_MECHANICS_RATIONALE_FIELDS = (
    "mechanic_expresses_edge",
    "entry_logic_rationale",
    "stop_loss_rationale",
    "target_exit_rationale",
    "profitability_rationale",
    "known_failure_modes",
)
SUPPORTED_CONTINUOUS_CONTRACT_RULES = {"none", "dominant_session_volume", "session_volume", "explicit_roll_calendar"}
DEFAULT_CAMPAIGN_VARIANT_COUNT = 5
MAX_CAMPAIGN_VARIANT_COUNT = 8
GOVERNANCE_CONTRACT_VERSION = 2
VARIANT_EXPANSION_RATIONALE_MIN_CHARS = 80
APPROVED_PRE_TEST_DECISIONS = {
    "approve_for_testing",
    "approve_for_density_screen",
    "approve_for_pre_pnl_density_audit",
    "approve_rescue_for_testing_after_density_audit",
}
TERMINAL_PRE_TEST_DECISIONS = {
    "blocked_by_campaign_density_failure",
    "reject_pre_pnl_density",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed research methodology preflight.")
    parser.add_argument("--config", action="append", dest="configs", help="Campaign config YAML to validate.")
    parser.add_argument(
        "--include-generated-results",
        action="store_true",
        help=(
            "Also inspect generated backtest-campaigns config snapshots. "
            "Default discovery checks authored active configs only."
        ),
    )
    parser.add_argument(
        "--allow-no-configs",
        action="store_true",
        help="Allow an empty config set. Intended only for wiring checks, not research approval.",
    )
    parser.add_argument("--skip-tests", action="store_true", help="Skip pytest execution.")
    parser.add_argument(
        "--pytest-args",
        default="tests",
        help="Arguments passed to pytest when tests are enabled. Default: tests",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--verbose", action="store_true", help="Print every warning instead of grouped summaries.")
    args = parser.parse_args(argv)

    result = run_preflight(
        config_paths=args.configs,
        include_generated_results=args.include_generated_results,
        allow_no_configs=args.allow_no_configs,
        run_tests=not args.skip_tests,
        pytest_args=shlex.split(args.pytest_args),
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_human_result(result, verbose=args.verbose)
    return 0 if result["passed"] else 1


def run_preflight(
    *,
    config_paths: Iterable[str | Path] | None = None,
    include_generated_results: bool = False,
    allow_no_configs: bool = False,
    run_tests: bool = True,
    pytest_args: Iterable[str] = ("tests",),
) -> dict:
    failures: list[str] = []
    warnings: list[str] = []
    paths = _config_paths(config_paths, include_generated_results=include_generated_results)

    if not paths and not allow_no_configs:
        failures.append(
            "No active authored campaign config files found. Pass --config or add configs under campaigns/ before research."
        )

    inspected = []
    data_validation_cache: dict[str, tuple[list[str], list[str]]] = {}
    data_cache_hits = 0
    terminal_configs = 0
    explicit_configs = config_paths is not None
    for path in paths:
        path = Path(path)
        inspected.append(str(_display_path(path)))
        try:
            cfg = _load_yaml(path)
            decision = _pre_test_decision(cfg)
            is_terminal = decision in TERMINAL_PRE_TEST_DECISIONS
            _validate_config(
                cfg,
                path,
                failures,
                warnings,
                allow_terminal_pretest=not explicit_configs,
            )
            _validate_campaign_variant_count(path, failures, warnings)
            _validate_campaign_governance(path, failures, warnings)
            if is_terminal and not explicit_configs:
                terminal_configs += 1
                continue
            if _validate_data(cfg, path, failures, warnings, cache=data_validation_cache):
                data_cache_hits += 1
        except Exception as exc:  # fail closed on malformed config or data loaders
            failures.append(f"{_display_path(path)}: preflight exception: {exc}")

    if run_tests:
        failures.extend(_pytest_failures(pytest_args))

    return {
        "passed": not failures,
        "configs_checked": inspected,
        "failures": failures,
        "warnings": warnings,
        "tests_ran": bool(run_tests),
        "include_generated_results": bool(include_generated_results),
        "data_sources_checked": len(data_validation_cache),
        "data_cache_hits": data_cache_hits,
        "terminal_configs_not_executed": terminal_configs,
    }


def _config_paths(
    config_paths: Iterable[str | Path] | None,
    *,
    include_generated_results: bool = False,
) -> list[Path]:
    if config_paths:
        return [Path(path) for path in config_paths]
    found: list[Path] = []
    patterns = list(ACTIVE_CONFIG_GLOBS)
    if include_generated_results:
        patterns.extend(GENERATED_RESULT_CONFIG_GLOBS)
    for pattern in patterns:
        found.extend(PROJECT_ROOT.glob(pattern))
    return sorted(path for path in found if path.is_file() and not _is_archived_path(path))


def _is_archived_path(path: Path) -> bool:
    return any(part == "_archived" or part.startswith("archive") for part in path.parts)


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"config file not found: {path}")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError("config YAML must load to a mapping")
    return loaded


def _validate_config(
    cfg: dict,
    path: Path,
    failures: list[str],
    warnings: list[str],
    *,
    allow_terminal_pretest: bool = False,
) -> None:
    prefix = str(_display_path(path))
    _require_keys(cfg, REQUIRED_TOP_LEVEL, prefix, failures)
    data_cfg = cfg.get("data") if isinstance(cfg.get("data"), dict) else {}
    strategy = cfg.get("strategy") if isinstance(cfg.get("strategy"), dict) else {}
    core = cfg.get("core") if isinstance(cfg.get("core"), dict) else {}
    apex = cfg.get("apex_rules") if isinstance(cfg.get("apex_rules"), dict) else {}

    if not data_cfg:
        failures.append(f"{prefix}: data must be a mapping.")
    elif not (data_cfg.get("timezone") or data_cfg.get("exchange_timezone")):
        failures.append(f"{prefix}: data.timezone or data.exchange_timezone is required for timestamp interpretation.")
    else:
        rule = data_cfg.get("continuous_contract")
        if rule is not None and str(rule) not in SUPPORTED_CONTINUOUS_CONTRACT_RULES:
            failures.append(
                f"{prefix}: data.continuous_contract={rule} is unsupported; expected one of "
                f"{sorted(SUPPORTED_CONTINUOUS_CONTRACT_RULES)}."
            )

    for section in ("entry", "tp", "sl"):
        value = strategy.get(section)
        if not isinstance(value, dict):
            failures.append(f"{prefix}: strategy.{section} must be configured.")
            continue
        _require_keys(value, ("module", "params"), f"{prefix}: strategy.{section}", failures)
        if not isinstance(value.get("params"), dict):
            failures.append(f"{prefix}: strategy.{section}.params must be a mapping.")
    _validate_strategy_module_registry(strategy, prefix, failures, warnings)
    if not strategy.get("flatten_time"):
        failures.append(f"{prefix}: strategy.flatten_time is required.")

    _require_keys(core, REQUIRED_CORE_FIELDS, f"{prefix}: core", failures)
    if "point_value" not in core and "tick_value" not in core:
        failures.append(f"{prefix}: core.point_value or core.tick_value is required.")
    elif "point_value" not in core:
        warnings.append(f"{prefix}: core.point_value is absent; engine will rely on core.tick_value.")
    if "contracts" not in core and "position_sizing" not in core:
        failures.append(f"{prefix}: core.contracts or core.position_sizing is required.")
    _require_positive(core, "tick_size", f"{prefix}: core", failures)
    if "point_value" in core:
        _require_positive(core, "point_value", f"{prefix}: core", failures)
    if "tick_value" in core:
        _require_positive(core, "tick_value", f"{prefix}: core", failures)
    _require_non_negative(core, "commission_per_contract", f"{prefix}: core", failures)
    _require_non_negative(core, "slippage_ticks", f"{prefix}: core", failures)

    if not apex:
        failures.append(f"{prefix}: apex_rules must be configured for prop-rule flatten checks.")
    else:
        if not bool(apex.get("enabled", False)):
            failures.append(f"{prefix}: apex_rules.enabled must be true for research preflight.")
        if not bool(apex.get("force_flatten_enabled", False)):
            failures.append(f"{prefix}: apex_rules.force_flatten_enabled must be true.")
        _require_keys(apex, REQUIRED_APEX_FIELDS, f"{prefix}: apex_rules", failures)

    _validate_parameter_grid(cfg, path, failures, warnings)
    _validate_minimum_target_rr(cfg, path, failures)
    _validate_mechanics_rationale(
        cfg,
        path,
        failures,
        warnings,
        allow_terminal_pretest=allow_terminal_pretest,
    )


def _validate_strategy_module_registry(
    strategy: dict,
    prefix: str,
    failures: list[str],
    warnings: list[str],
) -> None:
    entry = strategy.get("entry") if isinstance(strategy.get("entry"), dict) else {}
    tp = strategy.get("tp") if isinstance(strategy.get("tp"), dict) else {}
    sl = strategy.get("sl") if isinstance(strategy.get("sl"), dict) else {}
    entry_name = entry.get("module")
    tp_name = tp.get("module")
    sl_name = sl.get("module")
    if entry_name and entry_name not in ENTRY_MODULES:
        failures.append(f"{prefix}: unknown strategy.entry.module {entry_name!r}.")
    elif entry_name:
        metadata = entry_module_metadata(str(entry_name))
        if metadata.decision_timing not in {"bar_close", "intrabar", "bar_close_or_intrabar"}:
            failures.append(
                f"{prefix}: strategy.entry.module {entry_name!r} declares unsupported "
                f"decision_timing {metadata.decision_timing!r}."
            )
    if tp_name and tp_name not in TP_MODULES:
        failures.append(f"{prefix}: unknown strategy.tp.module {tp_name!r}.")
    if sl_name and sl_name not in SL_MODULES:
        failures.append(f"{prefix}: unknown strategy.sl.module {sl_name!r}.")


def _validate_mechanics_rationale(
    cfg: dict,
    path: Path,
    failures: list[str],
    warnings: list[str],
    *,
    allow_terminal_pretest: bool = False,
) -> None:
    prefix = str(_display_path(path))
    research = cfg.get("research_metadata")
    if not isinstance(research, dict):
        warnings.append(f"{prefix}: research_metadata is absent; new variants should include a mechanics review.")
        return
    required = bool(research.get("mechanics_review_required") or research.get("mechanics_review_version"))
    if not required:
        warnings.append(
            f"{prefix}: mechanics review is not marked required; new variants should set "
            "research_metadata.mechanics_review_required=true."
        )
        return

    review = research.get("mechanics_review")
    if not isinstance(review, dict):
        failures.append(f"{prefix}: research_metadata.mechanics_review must be configured for new variants.")
        return
    for field in REQUIRED_MECHANICS_RATIONALE_FIELDS:
        value = review.get(field)
        if not isinstance(value, str) or len(value.strip()) < 80:
            failures.append(
                f"{prefix}: research_metadata.mechanics_review.{field} must be a detailed pre-test rationale."
            )
    decision = str(review.get("pre_test_decision", "")).strip().lower()
    accepted = set(APPROVED_PRE_TEST_DECISIONS)
    if allow_terminal_pretest:
        accepted.update(TERMINAL_PRE_TEST_DECISIONS)
    if decision not in accepted:
        failures.append(
            f"{prefix}: research_metadata.mechanics_review.pre_test_decision {decision!r} is not an accepted "
            "pre-test lifecycle state."
        )


def _pre_test_decision(cfg: dict) -> str:
    research = cfg.get("research_metadata") if isinstance(cfg.get("research_metadata"), dict) else {}
    review = research.get("mechanics_review") if isinstance(research.get("mechanics_review"), dict) else {}
    return str(review.get("pre_test_decision") or "").strip().lower()


def _validate_parameter_grid(cfg: dict, path: Path, failures: list[str], warnings: list[str]) -> None:
    prefix = str(_display_path(path))
    for section in ("core_grid", "wfa"):
        container = cfg.get(section)
        if not isinstance(container, dict):
            continue
        params = container.get("parameters", {})
        if params is None:
            continue
        if not isinstance(params, dict):
            failures.append(f"{prefix}: {section}.parameters must be a mapping.")
            continue
        combo_count = 1
        entry_params = tp_params = sl_params = 0
        for key, values in params.items():
            if not isinstance(values, list) or not values:
                failures.append(f"{prefix}: {section}.parameters.{key} must be a non-empty list.")
                continue
            combo_count *= len(values)
            if key.startswith("entry.params."):
                entry_params += 1
            elif key.startswith("tp.params."):
                tp_params += 1
            elif key.startswith("sl.params."):
                sl_params += 1
        if combo_count > 120:
            failures.append(f"{prefix}: {section}.parameters has {combo_count} combinations; methodology cap is 120.")
        if entry_params > 2 or tp_params > 1 or sl_params > 1:
            failures.append(
                f"{prefix}: {section}.parameters exceeds methodology tunable count guidance "
                f"(entry={entry_params}, tp={tp_params}, sl={sl_params})."
            )


def _validate_minimum_target_rr(cfg: dict, path: Path, failures: list[str]) -> None:
    prefix = str(_display_path(path))
    for violation in target_rr_violations(cfg, minimum=MIN_TARGET_R_MULTIPLE, context=prefix):
        failures.append(
            f"{violation} is below the minimum allowed reward:risk target_r_multiple "
            f"{MIN_TARGET_R_MULTIPLE}."
        )


def _validate_campaign_variant_count(path: Path, failures: list[str], warnings: list[str]) -> None:
    campaign_root = _source_campaign_root(path)
    if campaign_root is None:
        return

    prefix = str(_display_path(path))
    campaign_yaml = campaign_root / "campaign.yaml"
    if not campaign_yaml.is_file():
        warnings.append(f"{prefix}: campaign.yaml is absent; variant-count policy could not be checked.")
        return

    campaign = _load_yaml(campaign_yaml)
    variants = campaign.get("variants")
    campaign_prefix = str(_display_path(campaign_yaml))
    if variants is None:
        warnings.append(f"{campaign_prefix}: variants list is absent; variant-count policy could not be checked.")
        return
    if not isinstance(variants, list):
        failures.append(f"{campaign_prefix}: variants must be a list.")
        return

    variant_count = len(variants)
    contract_version = int(campaign.get("governance_contract_version") or 0)
    if contract_version >= GOVERNANCE_CONTRACT_VERSION:
        if variant_count != DEFAULT_CAMPAIGN_VARIANT_COUNT:
            failures.append(
                f"{campaign_prefix}: governance contract v{contract_version} requires exactly "
                f"{DEFAULT_CAMPAIGN_VARIANT_COUNT} initial variants; found {variant_count}."
            )
        variant_dirs = {
            item.parent.name for item in (campaign_root / "variants").glob("*/config.yaml") if item.is_file()
        }
        declared = {str(item) for item in variants}
        if declared != variant_dirs:
            failures.append(
                f"{campaign_prefix}: declared variants must exactly match authored variants/*/config.yaml "
                f"(declared={sorted(declared)}, authored={sorted(variant_dirs)})."
            )
        return
    if variant_count > MAX_CAMPAIGN_VARIANT_COUNT:
        failures.append(
            f"{campaign_prefix}: campaign variant cap is {MAX_CAMPAIGN_VARIANT_COUNT}; found {variant_count} variants."
        )
    if variant_count > DEFAULT_CAMPAIGN_VARIANT_COUNT:
        rationale = campaign.get("variant_expansion_rationale")
        if not isinstance(rationale, str) or len(rationale.strip()) < VARIANT_EXPANSION_RATIONALE_MIN_CHARS:
            failures.append(
                f"{campaign_prefix}: campaigns with {variant_count} variants must include "
                "a detailed pre-test variant_expansion_rationale explaining why variants 6-8 "
                "are better distinct mechanics within the same edge."
            )


def _validate_campaign_governance(path: Path, failures: list[str], warnings: list[str]) -> None:
    campaign_root = _source_campaign_root(path)
    if campaign_root is None:
        return
    campaign_yaml = campaign_root / "campaign.yaml"
    if not campaign_yaml.is_file():
        return
    campaign = _load_yaml(campaign_yaml)
    if int(campaign.get("governance_contract_version") or 0) < GOVERNANCE_CONTRACT_VERSION:
        return

    prefix = str(_display_path(campaign_yaml))
    fingerprint = campaign.get("economic_edge_fingerprint")
    required_fingerprint = ("market_behavior", "causal_mechanism", "signal_inputs", "market_context", "holding_period")
    if not isinstance(fingerprint, dict):
        failures.append(f"{prefix}: economic_edge_fingerprint must be a mapping under governance contract v2.")
    else:
        for field in required_fingerprint:
            value = fingerprint.get(field)
            if not isinstance(value, str) or len(value.strip()) < 20:
                failures.append(f"{prefix}: economic_edge_fingerprint.{field} must be substantive and predeclared.")
        normalized = _normalized_fingerprint(fingerprint)
        if normalized:
            for other_path in sorted(PROJECT_ROOT.glob("campaigns/*/campaign.yaml")):
                if other_path.resolve() == campaign_yaml.resolve():
                    continue
                other = _load_yaml(other_path)
                other_fingerprint = other.get("economic_edge_fingerprint")
                if isinstance(other_fingerprint, dict) and _normalized_fingerprint(other_fingerprint) == normalized:
                    failures.append(
                        f"{prefix}: economic edge fingerprint duplicates {_display_path(other_path)}; "
                        "create no sibling campaign for the same economic edge."
                    )
                    break

    review = campaign.get("duplicate_edge_review")
    if not isinstance(review, dict):
        failures.append(f"{prefix}: duplicate_edge_review is required before campaign testing.")
    else:
        reviewed = review.get("reviewed_campaign_ids")
        ledger_queries = review.get("ledger_queries")
        if not isinstance(reviewed, list):
            failures.append(f"{prefix}: duplicate_edge_review.reviewed_campaign_ids must be a list.")
        if not isinstance(ledger_queries, list) or not ledger_queries:
            failures.append(f"{prefix}: duplicate_edge_review.ledger_queries must record at least one ledger search.")
        if str(review.get("conclusion") or "").lower() not in {"distinct", "duplicate_rejected"}:
            failures.append(f"{prefix}: duplicate_edge_review.conclusion must be distinct or duplicate_rejected.")
        distinction = review.get("substantive_distinction")
        if not isinstance(distinction, str) or len(distinction.strip()) < 80:
            failures.append(f"{prefix}: duplicate_edge_review.substantive_distinction must explain the economic difference.")

    variants = [str(item) for item in campaign.get("variants") or []]
    distinctions = campaign.get("variant_distinctions")
    if not isinstance(distinctions, dict):
        failures.append(f"{prefix}: variant_distinctions must document five materially different mechanics.")
    else:
        mechanics: list[str] = []
        for variant_id in variants:
            item = distinctions.get(variant_id)
            if not isinstance(item, dict):
                failures.append(f"{prefix}: variant_distinctions.{variant_id} is required.")
                continue
            mechanic = str(item.get("mechanic") or "").strip()
            difference = str(item.get("material_difference") or "").strip()
            if len(mechanic) < 40 or len(difference) < 40:
                failures.append(
                    f"{prefix}: variant_distinctions.{variant_id} must predeclare mechanic and material_difference."
                )
            mechanics.append(" ".join(mechanic.lower().split()))
        if len(set(mechanics)) != len(mechanics):
            failures.append(f"{prefix}: variant_distinctions contains duplicate mechanics.")

    rescue = campaign.get("rescue_policy")
    if not isinstance(rescue, dict):
        failures.append(f"{prefix}: rescue_policy is required.")
    else:
        maximum = rescue.get("max_rescues_per_failed_variant")
        if not isinstance(maximum, int) or maximum < 0 or maximum > 1:
            failures.append(f"{prefix}: rescue_policy.max_rescues_per_failed_variant must be 0 or 1.")
        rescue_root = campaign_root / "rescue_attempts"
        by_parent: dict[str, int] = {}
        if rescue_root.exists():
            for config in rescue_root.glob("*/*/config.yaml"):
                rescue_cfg = _load_yaml(config)
                parent = str((rescue_cfg.get("research_metadata") or {}).get("parent_variant_id") or "")
                if not parent:
                    failures.append(f"{_display_path(config)}: rescue must declare research_metadata.parent_variant_id.")
                    continue
                by_parent[parent] = by_parent.get(parent, 0) + 1
        for parent, count in by_parent.items():
            if isinstance(maximum, int) and count > maximum:
                failures.append(f"{prefix}: variant {parent} has {count} rescue attempts; maximum is {maximum}.")

    _validate_validation_gate_declaration(path, failures)
    _validate_attempt_declaration(path, campaign_root, failures)


def _validate_attempt_declaration(path: Path, campaign_root: Path, failures: list[str]) -> None:
    cfg = _load_yaml(path)
    prefix = str(_display_path(path))
    attempt_id = str(cfg.get("attempt_id") or "")
    if re.fullmatch(r"[a-z0-9][a-z0-9_]*", attempt_id) is None:
        failures.append(f"{prefix}: governance contract v2 requires a lowercase attempt_id.")
    if str(cfg.get("attempt_provenance") or "") != "authored":
        failures.append(f"{prefix}: governance contract v2 requires attempt_provenance=authored.")
    attempt_kind = str(cfg.get("attempt_kind") or "")
    if not attempt_kind:
        failures.append(f"{prefix}: governance contract v2 requires attempt_kind.")
    if "variants" in path.parts and attempt_kind and attempt_kind != "original":
        failures.append(f"{prefix}: initial variant attempts must use attempt_kind=original.")
    if attempt_kind and attempt_kind != "original" and not str(cfg.get("parent_attempt_id") or ""):
        failures.append(f"{prefix}: non-original attempts must declare parent_attempt_id.")

    if not attempt_id:
        return
    identity = (str(cfg.get("variant_id") or path.parent.name), attempt_id)
    matches = 0
    for config_path in campaign_root.rglob("config.yaml"):
        other = _load_yaml(config_path)
        other_identity = (str(other.get("variant_id") or config_path.parent.name), str(other.get("attempt_id") or ""))
        if other_identity == identity:
            matches += 1
    if matches > 1:
        failures.append(
            f"{prefix}: attempt identity {identity[0]}/{identity[1]} is declared by {matches} configs; it must be unique."
        )


def _validate_validation_gate_declaration(path: Path, failures: list[str]) -> None:
    cfg = _load_yaml(path)
    research = cfg.get("research_metadata") if isinstance(cfg.get("research_metadata"), dict) else {}
    gate = research.get("validation_gate") if isinstance(research.get("validation_gate"), dict) else None
    prefix = str(_display_path(path))
    if gate is None:
        failures.append(f"{prefix}: governance contract v2 requires research_metadata.validation_gate.")
        return
    if gate.get("required") is not True:
        failures.append(f"{prefix}: research_metadata.validation_gate.required must be true.")
    if str(gate.get("lane") or "") not in {"bar", "event_replay"}:
        failures.append(f"{prefix}: research_metadata.validation_gate.lane must be bar or event_replay.")
    for field in ("evidence_dir", "approval_path"):
        if not str(gate.get(field) or "").strip():
            failures.append(f"{prefix}: research_metadata.validation_gate.{field} is required.")
    subset = gate.get("data_subset")
    if not isinstance(subset, dict):
        failures.append(f"{prefix}: research_metadata.validation_gate.data_subset must be a deterministic date slice.")
    else:
        try:
            start = date.fromisoformat(str(subset.get("start_date")))
            end = date.fromisoformat(str(subset.get("end_date")))
            if end < start or (end - start).days > 14:
                failures.append(f"{prefix}: validation_gate.data_subset must span 0 to 14 calendar days.")
        except ValueError:
            failures.append(f"{prefix}: validation_gate.data_subset start_date/end_date must be ISO dates.")


def _normalized_fingerprint(value: dict) -> str:
    fields = ("market_behavior", "causal_mechanism", "signal_inputs", "market_context", "holding_period")
    if not all(isinstance(value.get(field), str) and value.get(field).strip() for field in fields):
        return ""
    return "|".join(" ".join(str(value[field]).lower().split()) for field in fields)


def _validate_data(
    cfg: dict,
    path: Path,
    failures: list[str],
    warnings: list[str],
    *,
    cache: dict[str, tuple[list[str], list[str]]] | None = None,
) -> bool:
    data_cfg = cfg.get("data")
    if not isinstance(data_cfg, dict):
        return False
    prefix = str(_display_path(path))
    _validate_data_paths(data_cfg, path, failures)
    if any(item.startswith(f"{prefix}: data path") for item in failures):
        return False
    load_cfg = _resolved_data_config(data_cfg, path)
    cache_key = _data_validation_cache_key(load_cfg)
    if cache is not None and cache_key in cache:
        cached_failures, cached_warnings = cache[cache_key]
        failures.extend(f"{prefix}: {message}" for message in cached_failures)
        warnings.extend(f"{prefix}: {message}" for message in cached_warnings)
        return True
    data_failures: list[str] = []
    data_warnings: list[str] = []
    try:
        df = load_raw_data(load_cfg)
    except Exception as exc:
        data_failures.append(f"data load failed: {exc}")
        _record_data_validation(cache, cache_key, data_failures, data_warnings)
        failures.extend(f"{prefix}: {message}" for message in data_failures)
        return False
    if df.empty:
        data_failures.append("data source loaded zero rows.")
    elif "timestamp" not in df.columns:
        data_failures.append("data source is missing timestamp column after load.")
    else:
        if not _timestamps_are_aware(df["timestamp"]):
            data_failures.append("timestamps are not timezone-aware after load.")
        duplicate_subset = _duplicate_subset(df)
        duplicate_count = int(df.duplicated(subset=duplicate_subset).sum())
        if duplicate_count:
            data_failures.append(f"data has {duplicate_count} duplicate bar(s) by {duplicate_subset}.")
        if not df["timestamp"].is_monotonic_increasing:
            data_warnings.append("loaded data timestamps are not monotonic before sorting.")
    _record_data_validation(cache, cache_key, data_failures, data_warnings)
    failures.extend(f"{prefix}: {message}" for message in data_failures)
    warnings.extend(f"{prefix}: {message}" for message in data_warnings)
    return False


def _record_data_validation(
    cache: dict[str, tuple[list[str], list[str]]] | None,
    key: str,
    failures: list[str],
    warnings: list[str],
) -> None:
    if cache is not None:
        cache[key] = (list(failures), list(warnings))


def _data_validation_cache_key(config: dict) -> str:
    source = infer_data_source(config)
    if source == "csv":
        relevant = {
            "source": source,
            "raw_csv": config.get("raw_csv"),
            "symbol": config.get("symbol", "ES"),
            "timezone": config.get("timezone", "America/Chicago"),
            "csv_format": config.get("csv_format", "standard"),
            "has_header": bool(config.get("has_header", True)),
            "timestamp_format": config.get("timestamp_format"),
        }
    elif source == "parquet":
        relevant = {
            "source": source,
            "raw_parquet": config.get("raw_parquet") or config.get("raw_csv"),
            "symbol": config.get("symbol", "ES"),
            "timezone": config.get("timezone", "America/Chicago"),
        }
    else:
        relevant = config
    return json.dumps(relevant, sort_keys=True, default=str, separators=(",", ":"))


def _validate_data_paths(data_cfg: dict, config_path: Path, failures: list[str]) -> None:
    prefix = str(_display_path(config_path))
    for key in ("raw_csv", "raw_parquet", "raw_dir"):
        value = data_cfg.get(key)
        if value and not _resolve_path(value, config_path).exists():
            failures.append(f"{prefix}: data path {key} does not exist: {value}")
    if not any(data_cfg.get(key) for key in ("raw_csv", "raw_parquet", "raw_dir")):
        failures.append(f"{prefix}: data.raw_csv, data.raw_parquet, or data.raw_dir is required.")


def _resolved_data_config(data_cfg: dict, config_path: Path) -> dict:
    out = dict(data_cfg)
    for key in ("raw_csv", "raw_parquet", "raw_dir"):
        if out.get(key):
            out[key] = str(_resolve_path(out[key], config_path))
    return out


def _source_campaign_root(config_path: Path) -> Path | None:
    parts = config_path.parts
    if "campaigns" not in parts:
        return None
    campaigns_index = len(parts) - 1 - list(reversed(parts)).index("campaigns")
    if len(parts) <= campaigns_index + 1:
        return None
    return Path(*parts[: campaigns_index + 2])


def _resolve_path(value: str | Path, config_path: Path) -> Path:
    path = Path(value)
    if path.is_absolute() or path.exists():
        return path
    candidate = config_path.parent / path
    return candidate if candidate.exists() else PROJECT_ROOT / path


def _timestamps_are_aware(series: pd.Series) -> bool:
    if isinstance(series.dtype, pd.DatetimeTZDtype):
        return True
    try:
        values = pd.to_datetime(series, errors="raise")
    except Exception:
        return False
    if isinstance(values.dtype, pd.DatetimeTZDtype):
        return True
    return all(pd.Timestamp(value).tzinfo is not None for value in values.dropna())


def _duplicate_subset(df: pd.DataFrame) -> list[str]:
    subset = ["timestamp"]
    for column in ("symbol", "contract_symbol"):
        if column in df.columns:
            subset.append(column)
    return subset


def _pytest_failures(pytest_args: Iterable[str]) -> list[str]:
    args = list(pytest_args)
    cmd = [sys.executable, "-m", "pytest", *args]
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True, capture_output=True)
    if proc.returncode == 0:
        return []
    tail = "\n".join((proc.stdout + "\n" + proc.stderr).splitlines()[-80:])
    return [f"pytest failed with exit code {proc.returncode}: {' '.join(cmd)}\n{tail}"]


def _require_keys(container: dict, keys: Iterable[str], prefix: str, failures: list[str]) -> None:
    for key in keys:
        if key not in container or container.get(key) in (None, ""):
            failures.append(f"{prefix}: missing required key {key}.")


def _require_positive(container: dict, key: str, prefix: str, failures: list[str]) -> None:
    if key not in container:
        return
    try:
        value = float(container[key])
    except (TypeError, ValueError):
        failures.append(f"{prefix}.{key} must be numeric.")
        return
    if value <= 0:
        failures.append(f"{prefix}.{key} must be greater than 0.")


def _require_non_negative(container: dict, key: str, prefix: str, failures: list[str]) -> None:
    if key not in container:
        return
    try:
        value = float(container[key])
    except (TypeError, ValueError):
        failures.append(f"{prefix}.{key} must be numeric.")
        return
    if value < 0:
        failures.append(f"{prefix}.{key} must be greater than or equal to 0.")


def _print_human_result(result: dict, *, verbose: bool = False) -> None:
    status = "PASS" if result["passed"] else "FAIL"
    print(f"Preflight {status}")
    print(f"Configs checked: {len(result['configs_checked'])}")
    print(f"Tests ran: {result['tests_ran']}")
    print(f"Distinct data sources checked: {result['data_sources_checked']}")
    print(f"Reused data validations: {result['data_cache_hits']}")
    print(f"Terminal configs not executed: {result['terminal_configs_not_executed']}")
    warnings = result["warnings"]
    print(f"Warnings: {len(warnings)}")
    if verbose:
        for warning in warnings:
            print(f"WARNING: {warning}")
    else:
        grouped: dict[str, list[str]] = defaultdict(list)
        for warning in warnings:
            location, separator, message = warning.partition(": ")
            grouped[message if separator else warning].append(location if separator else "")
        for message, locations in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
            examples = ", ".join(location for location in locations[:3] if location)
            suffix = f" Examples: {examples}" if examples else ""
            print(f"WARNING x{len(locations)}: {message}{suffix}")
    for failure in result["failures"]:
        print(f"FAIL: {failure}")


def _display_path(path: Path) -> Path:
    try:
        return path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        return path


if __name__ == "__main__":
    raise SystemExit(main())
