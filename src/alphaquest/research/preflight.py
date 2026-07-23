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

from alphaquest.data.clean import apply_continuous_contract, validate_ohlc  # noqa: E402
from alphaquest.data.load import infer_data_source, load_raw_data  # noqa: E402
from alphaquest.data.sessions import assign_sessions  # noqa: E402
from alphaquest.research.storage import (  # noqa: E402
    campaign_definition_paths,
    load_storage_layout,
    resolve_campaign_context,
    resolve_recorded_path,
)
from alphaquest.strategy_modules.entry import ENTRY_MODULES, entry_module_metadata  # noqa: E402
from alphaquest.strategy_certification import (  # noqa: E402
    StrategyCertificationError,
    get_strategy_certification,
    normalize_certified_event_params,
    strategy_identity_for_config,
    validate_certified_event_parameter_grid,
)
from alphaquest.strategy_modules.sl import SL_MODULES  # noqa: E402
from alphaquest.strategy_modules.tp import TP_MODULES  # noqa: E402
from alphaquest.utils.hashing import file_sha256  # noqa: E402
from alphaquest.utils.target_rr import MIN_TARGET_R_MULTIPLE, target_rr_violations  # noqa: E402


ACTIVE_CONFIG_GLOBS = (
    "campaigns/**/variants/**/config.yaml",
    "campaigns/**/rescue_attempts/**/config.yaml",
    "campaigns/**/follow_up_attempts/**/config.yaml",
    "configs/campaigns/**/*.yaml",
)
GENERATED_RESULT_CONFIG_GLOBS = (
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
DEFAULT_CAMPAIGN_VARIANT_COUNT = 1
MAX_CAMPAIGN_VARIANT_COUNT = 5
GOVERNANCE_CONTRACT_VERSION = 2
SEQUENTIAL_GOVERNANCE_CONTRACT_VERSION = 3
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
    parser.add_argument(
        "--project-root",
        default=None,
        help="Workspace root used for storage layout, relative data paths, duplicate scans, and tests.",
    )
    args = parser.parse_args(argv)

    result = run_preflight(
        config_paths=args.configs,
        include_generated_results=args.include_generated_results,
        allow_no_configs=args.allow_no_configs,
        run_tests=not args.skip_tests,
        pytest_args=shlex.split(args.pytest_args),
        project_root=args.project_root,
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
    project_root: str | Path | None = None,
) -> dict:
    root = _resolved_project_root(project_root)
    failures: list[str] = []
    warnings: list[str] = []
    paths = _config_paths(
        config_paths,
        include_generated_results=include_generated_results,
        project_root=root,
    )

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
        inspected.append(str(_display_path(path, project_root=root)))
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
                project_root=root,
            )
            _validate_campaign_variant_count(path, failures, warnings, project_root=root)
            _validate_campaign_governance(path, failures, warnings, project_root=root)
            if is_terminal and not explicit_configs:
                terminal_configs += 1
                continue
            if _validate_data(
                cfg,
                path,
                failures,
                warnings,
                cache=data_validation_cache,
                project_root=root,
            ):
                data_cache_hits += 1
        except Exception as exc:  # fail closed on malformed config or data loaders
            failures.append(f"{_display_path(path, project_root=root)}: preflight exception: {exc}")

    if run_tests:
        failures.extend(_pytest_failures(pytest_args, project_root=root))

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
    project_root: str | Path | None = None,
) -> list[Path]:
    root = _resolved_project_root(project_root)
    if config_paths:
        return [path if (path := Path(value)).is_absolute() else root / path for value in config_paths]
    layout = load_storage_layout(root)
    found: set[Path] = set()
    if layout.active_campaign_root.is_dir():
        found.update(layout.active_campaign_root.glob("*/variants/*/config.yaml"))
        found.update(layout.active_campaign_root.glob("*/rescue_attempts/*/*/config.yaml"))
        found.update(layout.active_campaign_root.glob("*/follow_up_attempts/*/*/config.yaml"))
    if include_generated_results:
        for evidence_root in layout.evidence_roots:
            if not evidence_root.is_dir():
                continue
            found.update(evidence_root.glob("**/effective_config.yaml"))
            found.update(evidence_root.glob("**/config.yaml"))

    patterns = list(ACTIVE_CONFIG_GLOBS)
    if include_generated_results:
        patterns.extend(GENERATED_RESULT_CONFIG_GLOBS)
    for pattern in patterns:
        found.update(
            path
            for path in root.glob(pattern)
            if path.is_file() and not _is_archived_path(path)
        )
    return sorted(path for path in found if path.is_file())


def _is_archived_path(path: Path) -> bool:
    return any(part == "_archived" or part.startswith("archive") for part in path.parts)


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"config file not found: {path}")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError("config YAML must load to a mapping")
    return loaded


def _load_json(path: Path) -> dict:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _validate_config(
    cfg: dict,
    path: Path,
    failures: list[str],
    warnings: list[str],
    *,
    allow_terminal_pretest: bool = False,
    project_root: str | Path | None = None,
) -> None:
    prefix = str(_display_path(path, project_root=project_root))
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
        if str(rule) == "explicit_roll_calendar" and not data_cfg.get("roll_calendar"):
            failures.append(f"{prefix}: data.roll_calendar is required for explicit_roll_calendar.")

    for section in ("entry", "tp", "sl"):
        value = strategy.get(section)
        if not isinstance(value, dict):
            failures.append(f"{prefix}: strategy.{section} must be configured.")
            continue
        _require_keys(value, ("module", "params"), f"{prefix}: strategy.{section}", failures)
        if not isinstance(value.get("params"), dict):
            failures.append(f"{prefix}: strategy.{section}.params must be a mapping.")
    _validate_strategy_module_registry(
        strategy,
        prefix,
        failures,
        warnings,
        engine_lane=str(cfg.get("engine_lane") or "bar"),
    )
    if str(cfg.get("engine_lane") or "") == "canonical_event_replay":
        try:
            strategy_identity_for_config(
                cfg,
                _resolved_project_root(project_root),
                require_declared_match=True,
            )
        except StrategyCertificationError as exc:
            failures.append(f"{prefix}: strategy implementation certification failed: {exc}")
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

    _validate_parameter_grid(cfg, path, failures, warnings, project_root=project_root)
    _validate_minimum_target_rr(cfg, path, failures, project_root=project_root)
    _validate_mechanics_rationale(
        cfg,
        path,
        failures,
        warnings,
        allow_terminal_pretest=allow_terminal_pretest,
        project_root=project_root,
    )


def _validate_strategy_module_registry(
    strategy: dict,
    prefix: str,
    failures: list[str],
    warnings: list[str],
    *,
    engine_lane: str = "bar",
) -> None:
    entry = strategy.get("entry") if isinstance(strategy.get("entry"), dict) else {}
    tp = strategy.get("tp") if isinstance(strategy.get("tp"), dict) else {}
    sl = strategy.get("sl") if isinstance(strategy.get("sl"), dict) else {}
    entry_name = entry.get("module")
    tp_name = tp.get("module")
    sl_name = sl.get("module")
    if engine_lane == "canonical_event_replay":
        event = strategy.get("event") if isinstance(strategy.get("event"), dict) else {}
        event_name = event.get("module")
        try:
            certification = get_strategy_certification(str(event_name or ""), require_current=True)
        except StrategyCertificationError as exc:
            failures.append(f"{prefix}: strategy certification failed: {exc}")
            return
        if entry_name != certification.entry_module:
            failures.append(f"{prefix}: event entry module does not match the strategy certification.")
        if tp_name != certification.target_module:
            failures.append(f"{prefix}: event TP module does not match the strategy certification.")
        if sl_name != certification.stop_module:
            failures.append(f"{prefix}: event SL module does not match the strategy certification.")
        return
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
    project_root: str | Path | None = None,
) -> None:
    prefix = str(_display_path(path, project_root=project_root))
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


def _validate_parameter_grid(
    cfg: dict,
    path: Path,
    failures: list[str],
    warnings: list[str],
    *,
    project_root: str | Path | None = None,
) -> None:
    prefix = str(_display_path(path, project_root=project_root))
    if str(cfg.get("engine_lane") or "") == "canonical_event_replay":
        strategy = cfg.get("strategy") if isinstance(cfg.get("strategy"), dict) else {}
        event = strategy.get("event") if isinstance(strategy.get("event"), dict) else {}
        try:
            certification = get_strategy_certification(
                str(event.get("module") or ""),
                _resolved_project_root(project_root),
                require_current=True,
            )
            event_params = normalize_certified_event_params(
                certification,
                event.get("params") if isinstance(event.get("params"), dict) else {},
            )
            if event_params != event.get("params"):
                failures.append(
                    f"{prefix}: strategy.event.params must explicitly contain every certified default."
                )
            core_params = (cfg.get("core_grid") or {}).get("parameters", {})
            wfa_params = (cfg.get("wfa") or {}).get("parameters", {})
            if core_params != wfa_params:
                failures.append(
                    f"{prefix}: certified event core_grid.parameters and wfa.parameters must be identical."
                )
            validate_certified_event_parameter_grid(
                certification,
                event_params,
                core_params if isinstance(core_params, dict) else {},
                qualified_keys=True,
            )
        except StrategyCertificationError as exc:
            failures.append(f"{prefix}: certified event parameter declaration failed: {exc}")
        return
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


def _validate_minimum_target_rr(
    cfg: dict,
    path: Path,
    failures: list[str],
    *,
    project_root: str | Path | None = None,
) -> None:
    prefix = str(_display_path(path, project_root=project_root))
    for violation in target_rr_violations(cfg, minimum=MIN_TARGET_R_MULTIPLE, context=prefix):
        failures.append(
            f"{violation} is below the minimum allowed reward:risk target_r_multiple "
            f"{MIN_TARGET_R_MULTIPLE}."
        )


def _validate_campaign_variant_count(
    path: Path,
    failures: list[str],
    warnings: list[str],
    *,
    project_root: str | Path | None = None,
) -> None:
    campaign_root = _source_campaign_root(path, project_root=project_root)
    if campaign_root is None:
        return

    prefix = str(_display_path(path, project_root=project_root))
    campaign_yaml = campaign_root / "campaign.yaml"
    if not campaign_yaml.is_file():
        warnings.append(f"{prefix}: campaign.yaml is absent; variant-count policy could not be checked.")
        return

    campaign = _load_yaml(campaign_yaml)
    variants = campaign.get("variants")
    campaign_prefix = str(_display_path(campaign_yaml, project_root=project_root))
    if variants is None:
        warnings.append(f"{campaign_prefix}: variants list is absent; variant-count policy could not be checked.")
        return
    if not isinstance(variants, list):
        failures.append(f"{campaign_prefix}: variants must be a list.")
        return

    variant_count = len(variants)
    contract_version = int(campaign.get("governance_contract_version") or 0)
    if contract_version >= SEQUENTIAL_GOVERNANCE_CONTRACT_VERSION:
        if not 1 <= variant_count <= MAX_CAMPAIGN_VARIANT_COUNT:
            failures.append(
                f"{campaign_prefix}: governance contract v{contract_version} requires between 1 and "
                f"{MAX_CAMPAIGN_VARIANT_COUNT} sequential variants; found {variant_count}."
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
        history = campaign.get("sequential_variant_history")
        if variant_count > 1 and (not isinstance(history, list) or len(history) != variant_count - 1):
            failures.append(
                f"{campaign_prefix}: campaigns with {variant_count} variants must include "
                "failure-informed sequential_variant_history for every added variant."
            )
        elif isinstance(history, list):
            root = _resolved_project_root(project_root)
            ids = [str(item) for item in variants]
            for index, item in enumerate(history, start=1):
                if not isinstance(item, dict):
                    failures.append(f"{campaign_prefix}: sequential_variant_history[{index - 1}] must be a mapping.")
                    continue
                if (
                    str(item.get("variant_id") or "") != ids[index]
                    or str(item.get("predecessor_variant_id") or "") != ids[index - 1]
                    or str(item.get("predecessor_verdict") or "") != "FAIL"
                ):
                    failures.append(f"{campaign_prefix}: sequential_variant_history[{index - 1}] breaks variant order.")
                if len(str(item.get("failure_analysis") or "").strip()) < 80:
                    failures.append(f"{campaign_prefix}: sequential_variant_history[{index - 1}] needs an 80-character failure analysis.")
                recorded = str(item.get("predecessor_result_path") or "")
                result_path = resolve_recorded_path(recorded, project_root=root) if recorded else None
                expected_hash = str(item.get("predecessor_result_sha256") or "")
                if result_path is None or not result_path.is_file():
                    failures.append(f"{campaign_prefix}: predecessor FAIL result is missing for {ids[index]}.")
                elif file_sha256(result_path) != expected_hash:
                    failures.append(f"{campaign_prefix}: predecessor FAIL result hash drifted for {ids[index]}.")
                else:
                    result = _load_json(result_path)
                    verdict = str(result.get("verdict") or result.get("research_verdict") or result.get("decision") or "")
                    if verdict != "FAIL":
                        failures.append(f"{campaign_prefix}: predecessor result for {ids[index]} is not terminal FAIL.")
        return
    if contract_version >= GOVERNANCE_CONTRACT_VERSION:
        if variant_count != 5:
            failures.append(
                f"{campaign_prefix}: governance contract v{contract_version} requires exactly 5 initial variants; "
                f"found {variant_count}."
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


def _validate_campaign_governance(
    path: Path,
    failures: list[str],
    warnings: list[str],
    *,
    project_root: str | Path | None = None,
) -> None:
    root = _resolved_project_root(project_root)
    campaign_root = _source_campaign_root(path, project_root=root)
    if campaign_root is None:
        return
    campaign_yaml = campaign_root / "campaign.yaml"
    if not campaign_yaml.is_file():
        return
    campaign = _load_yaml(campaign_yaml)
    if int(campaign.get("governance_contract_version") or 0) < GOVERNANCE_CONTRACT_VERSION:
        return

    prefix = str(_display_path(campaign_yaml, project_root=root))
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
            for other_path in campaign_definition_paths(project_root=root):
                if other_path.resolve() == campaign_yaml.resolve():
                    continue
                other = _load_yaml(other_path)
                other_fingerprint = other.get("economic_edge_fingerprint")
                if isinstance(other_fingerprint, dict) and _normalized_fingerprint(other_fingerprint) == normalized:
                    failures.append(
                        f"{prefix}: economic edge fingerprint duplicates "
                        f"{_display_path(other_path, project_root=root)}; "
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
        failures.append(f"{prefix}: variant_distinctions must document every declared mechanic.")
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
        by_parent: dict[str, set[str]] = {}
        for config in campaign_root.rglob("config.yaml"):
            rescue_cfg = _load_yaml(config)
            is_legacy_rescue_path = "rescue_attempts" in config.relative_to(campaign_root).parts
            if str(rescue_cfg.get("attempt_kind") or "") != "rescue" and not is_legacy_rescue_path:
                continue
            research = rescue_cfg.get("research_metadata") or {}
            parent = str(
                research.get("rescue_target_variant_id")
                or research.get("parent_variant_id")
                or ""
            )
            if not parent:
                failures.append(
                    f"{_display_path(config, project_root=root)}: rescue must declare "
                    "research_metadata.rescue_target_variant_id or parent_variant_id."
                )
                continue
            if is_legacy_rescue_path:
                relative = config.relative_to(campaign_root / "rescue_attempts")
                path_attempt_id = relative.parts[0]
            else:
                path_attempt_id = str(config.parent)
            attempt_id = str(rescue_cfg.get("attempt_id") or path_attempt_id)
            by_parent.setdefault(parent, set()).add(attempt_id)
        if by_parent and rescue.get("allowed") is not True:
            failures.append(f"{prefix}: authored rescue attempts exist but rescue_policy.allowed is not true.")
        for parent, attempts in by_parent.items():
            count = len(attempts)
            if isinstance(maximum, int) and count > maximum:
                failures.append(f"{prefix}: variant {parent} has {count} rescue attempts; maximum is {maximum}.")

    _validate_validation_gate_declaration(path, failures, project_root=root)
    _validate_attempt_declaration(path, campaign_root, failures, project_root=root)


def _validate_attempt_declaration(
    path: Path,
    campaign_root: Path,
    failures: list[str],
    *,
    project_root: str | Path | None = None,
) -> None:
    cfg = _load_yaml(path)
    prefix = str(_display_path(path, project_root=project_root))
    attempt_id = str(cfg.get("attempt_id") or "")
    if re.fullmatch(r"[a-z0-9][a-z0-9_]*", attempt_id) is None:
        failures.append(f"{prefix}: governance contract v2 requires a lowercase attempt_id.")
    if str(cfg.get("attempt_provenance") or "") != "authored":
        failures.append(f"{prefix}: governance contract v2 requires attempt_provenance=authored.")
    attempt_kind = str(cfg.get("attempt_kind") or "")
    if not attempt_kind:
        failures.append(f"{prefix}: governance contract v2 requires attempt_kind.")
    try:
        relative = path.resolve().relative_to(campaign_root.resolve())
    except ValueError:
        relative = path
    if relative.parts and relative.parts[0] == "variants" and attempt_kind and attempt_kind != "original":
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


def _validate_validation_gate_declaration(
    path: Path,
    failures: list[str],
    *,
    project_root: str | Path | None = None,
) -> None:
    cfg = _load_yaml(path)
    research = cfg.get("research_metadata") if isinstance(cfg.get("research_metadata"), dict) else {}
    gate = research.get("validation_gate") if isinstance(research.get("validation_gate"), dict) else None
    prefix = str(_display_path(path, project_root=project_root))
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
    project_root: str | Path | None = None,
) -> bool:
    data_cfg = cfg.get("data")
    if not isinstance(data_cfg, dict):
        return False
    prefix = str(_display_path(path, project_root=project_root))
    _validate_data_paths(data_cfg, path, failures, project_root=project_root)
    if any(item.startswith(f"{prefix}: data path") for item in failures):
        return False
    if str(cfg.get("engine_lane") or "") == "canonical_event_replay":
        execution = data_cfg.get("execution_data") if isinstance(data_cfg.get("execution_data"), dict) else {}
        source = str(execution.get("source") or "")
        if source not in {"databento_zip_trades", "databento_trades_zip", "sierra_scid_records"}:
            failures.append(f"{prefix}: canonical event replay requires a certified governed event source.")
            return False
        if source == "sierra_scid_records":
            if execution.get("required_capability") not in {
                "full_strategy_events",
                "full_strategy_events_extrapolated",
            }:
                failures.append(f"{prefix}: Sierra event replay requires an approved strategy capability.")
                return False
            if execution.get("ineligible_session_policy") not in {"error", "blackout"}:
                failures.append(f"{prefix}: Sierra event replay requires a fail-closed session policy.")
                return False
            if (
                str(execution.get("rth_start") or "") != "09:30:00"
                or str(execution.get("rth_end") or "") != "11:00:00"
            ):
                failures.append(f"{prefix}: Sierra event replay is certified only for 09:30-11:00 ET.")
                return False
        return True
    load_cfg = _resolved_data_config(data_cfg, path, project_root=project_root)
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
        invalid_ohlcv = int((~validate_ohlc(df)).sum())
        if invalid_ohlcv:
            data_failures.append(
                f"data has {invalid_ohlcv} non-finite, non-positive, negative-volume, or inconsistent OHLCV row(s)."
            )
        if "row_quality_valid" in df.columns:
            flagged = int((df["row_quality_valid"] != True).sum())  # noqa: E712 - explicit data comparison
            if flagged:
                data_failures.append(f"governed source still contains {flagged} row(s) flagged invalid at intake.")
        rule = str(load_cfg.get("continuous_contract") or "none")
        if rule not in {"", "none", "false"}:
            try:
                selected = apply_continuous_contract(assign_sessions(df, load_cfg), load_cfg)
            except Exception as exc:
                data_failures.append(f"continuous-contract selection failed: {exc}")
            else:
                if selected.empty:
                    data_failures.append("continuous-contract selection produced zero bars.")
                selected_duplicates = int(selected.duplicated(subset=["timestamp", "symbol"]).sum())
                if selected_duplicates:
                    data_failures.append(
                        f"continuous-contract selection left {selected_duplicates} duplicate timestamp/symbol bar(s)."
                    )
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
            "continuous_contract": config.get("continuous_contract"),
            "roll_calendar": config.get("roll_calendar"),
        }
    elif source == "parquet":
        relevant = {
            "source": source,
            "raw_parquet": config.get("raw_parquet") or config.get("raw_csv"),
            "symbol": config.get("symbol", "ES"),
            "timezone": config.get("timezone", "America/Chicago"),
            "continuous_contract": config.get("continuous_contract"),
            "roll_calendar": config.get("roll_calendar"),
        }
    else:
        relevant = config
    return json.dumps(relevant, sort_keys=True, default=str, separators=(",", ":"))


def _validate_data_paths(
    data_cfg: dict,
    config_path: Path,
    failures: list[str],
    *,
    project_root: str | Path | None = None,
) -> None:
    prefix = str(_display_path(config_path, project_root=project_root))
    for key in ("raw_csv", "raw_parquet", "raw_dir", "roll_calendar"):
        value = data_cfg.get(key)
        if value and not _resolve_path(value, config_path, project_root=project_root).exists():
            failures.append(f"{prefix}: data path {key} does not exist: {value}")
    roll_calendar = data_cfg.get("roll_calendar")
    expected_roll_hash = data_cfg.get("roll_calendar_sha256")
    if roll_calendar and expected_roll_hash:
        resolved_roll = _resolve_path(roll_calendar, config_path, project_root=project_root)
        if resolved_roll.is_file() and file_sha256(resolved_roll) != str(expected_roll_hash):
            failures.append(f"{prefix}: data.roll_calendar_sha256 does not match {roll_calendar}.")
    if not any(data_cfg.get(key) for key in ("raw_csv", "raw_parquet", "raw_dir")):
        failures.append(f"{prefix}: data.raw_csv, data.raw_parquet, or data.raw_dir is required.")
    execution = data_cfg.get("execution_data") if isinstance(data_cfg.get("execution_data"), dict) else {}
    for key in (
        "archive",
        "roll_calendar",
        "raw_manifest",
        "session_levels",
        "quality_manifest",
        "concordance_report",
    ):
        value = execution.get(key)
        if value and not _resolve_path(value, config_path, project_root=project_root).is_file():
            failures.append(f"{prefix}: data path execution_data.{key} does not exist: {value}")
    raw_dir = execution.get("raw_dir")
    if raw_dir and not _resolve_path(raw_dir, config_path, project_root=project_root).is_dir():
        failures.append(f"{prefix}: data path execution_data.raw_dir does not exist: {raw_dir}")
    for key in (
        "archive",
        "roll_calendar",
        "raw_manifest",
        "session_levels",
        "quality_manifest",
        "concordance_report",
    ):
        value = execution.get(key)
        expected = execution.get(f"{key}_sha256")
        if value and expected:
            resolved = _resolve_path(value, config_path, project_root=project_root)
            if resolved.is_file() and file_sha256(resolved) != str(expected):
                failures.append(
                    f"{prefix}: data.execution_data.{key}_sha256 does not match {value}."
                )


def _resolved_data_config(
    data_cfg: dict,
    config_path: Path,
    *,
    project_root: str | Path | None = None,
) -> dict:
    out = dict(data_cfg)
    for key in ("raw_csv", "raw_parquet", "raw_dir", "roll_calendar"):
        if out.get(key):
            out[key] = str(_resolve_path(out[key], config_path, project_root=project_root))
    execution = out.get("execution_data")
    if isinstance(execution, dict):
        execution = dict(execution)
        for key in (
            "archive",
            "roll_calendar",
            "raw_dir",
            "raw_manifest",
            "session_levels",
            "quality_manifest",
            "concordance_report",
        ):
            if execution.get(key):
                execution[key] = str(
                    _resolve_path(execution[key], config_path, project_root=project_root)
                )
        out["execution_data"] = execution
    return out


def _source_campaign_root(
    config_path: Path,
    *,
    project_root: str | Path | None = None,
) -> Path | None:
    context = resolve_campaign_context(
        config_path,
        project_root=_resolved_project_root(project_root),
    )
    return context.campaign_root if context is not None else None


def _resolve_path(
    value: str | Path,
    config_path: Path,
    *,
    project_root: str | Path | None = None,
) -> Path:
    root = _resolved_project_root(project_root)
    path = Path(value)
    if path.is_absolute():
        return path
    candidate = config_path.parent / path
    return candidate if candidate.exists() else root / path


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


def _pytest_failures(
    pytest_args: Iterable[str],
    *,
    project_root: str | Path | None = None,
) -> list[str]:
    args = list(pytest_args)
    cmd = [sys.executable, "-m", "pytest", *args]
    proc = subprocess.run(cmd, cwd=_resolved_project_root(project_root), text=True, capture_output=True)
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


def _resolved_project_root(value: str | Path | None) -> Path:
    return Path(PROJECT_ROOT if value is None else value).resolve()


def _display_path(path: Path, *, project_root: str | Path | None = None) -> Path:
    root = _resolved_project_root(project_root)
    try:
        return path.resolve().relative_to(root)
    except ValueError:
        return path


if __name__ == "__main__":
    raise SystemExit(main())
