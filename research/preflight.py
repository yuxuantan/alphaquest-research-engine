from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Iterable

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from propstack.data.load import load_raw_data  # noqa: E402


DEFAULT_CONFIG_GLOBS = (
    "backtest-campaigns/**/effective_config.yaml",
    "backtest-campaigns/**/config.yaml",
    "campaigns/**/variants/**/config.yaml",
    "configs/campaigns/**/*.yaml",
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed research methodology preflight.")
    parser.add_argument("--config", action="append", dest="configs", help="Campaign config YAML to validate.")
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
    args = parser.parse_args(argv)

    result = run_preflight(
        config_paths=args.configs,
        allow_no_configs=args.allow_no_configs,
        run_tests=not args.skip_tests,
        pytest_args=shlex.split(args.pytest_args),
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_human_result(result)
    return 0 if result["passed"] else 1


def run_preflight(
    *,
    config_paths: Iterable[str | Path] | None = None,
    allow_no_configs: bool = False,
    run_tests: bool = True,
    pytest_args: Iterable[str] = ("tests",),
) -> dict:
    failures: list[str] = []
    warnings: list[str] = []
    paths = _config_paths(config_paths)

    if not paths and not allow_no_configs:
        failures.append(
            "No active campaign config files found. Pass --config or restore backtest-campaigns/configs before research."
        )

    inspected = []
    for path in paths:
        path = Path(path)
        inspected.append(str(_display_path(path)))
        try:
            cfg = _load_yaml(path)
            _validate_config(cfg, path, failures, warnings)
            _validate_data(cfg, path, failures, warnings)
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
    }


def _config_paths(config_paths: Iterable[str | Path] | None) -> list[Path]:
    if config_paths:
        return [Path(path) for path in config_paths]
    found: list[Path] = []
    for pattern in DEFAULT_CONFIG_GLOBS:
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


def _validate_config(cfg: dict, path: Path, failures: list[str], warnings: list[str]) -> None:
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

    for section in ("entry", "tp", "sl"):
        value = strategy.get(section)
        if not isinstance(value, dict):
            failures.append(f"{prefix}: strategy.{section} must be configured.")
            continue
        _require_keys(value, ("module", "params"), f"{prefix}: strategy.{section}", failures)
        if not isinstance(value.get("params"), dict):
            failures.append(f"{prefix}: strategy.{section}.params must be a mapping.")
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
    _validate_mechanics_rationale(cfg, path, failures, warnings)


def _validate_mechanics_rationale(cfg: dict, path: Path, failures: list[str], warnings: list[str]) -> None:
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
    if decision != "approve_for_testing":
        failures.append(
            f"{prefix}: research_metadata.mechanics_review.pre_test_decision must be approve_for_testing."
        )


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


def _validate_data(cfg: dict, path: Path, failures: list[str], warnings: list[str]) -> None:
    data_cfg = cfg.get("data")
    if not isinstance(data_cfg, dict):
        return
    prefix = str(_display_path(path))
    _validate_data_paths(data_cfg, path, failures)
    if any(item.startswith(f"{prefix}: data path") for item in failures):
        return
    load_cfg = _resolved_data_config(data_cfg, path)
    try:
        df = load_raw_data(load_cfg)
    except Exception as exc:
        failures.append(f"{prefix}: data load failed: {exc}")
        return
    if df.empty:
        failures.append(f"{prefix}: data source loaded zero rows.")
        return
    if "timestamp" not in df.columns:
        failures.append(f"{prefix}: data source is missing timestamp column after load.")
        return
    if not _timestamps_are_aware(df["timestamp"]):
        failures.append(f"{prefix}: timestamps are not timezone-aware after load.")
    duplicate_subset = _duplicate_subset(df)
    duplicate_count = int(df.duplicated(subset=duplicate_subset).sum())
    if duplicate_count:
        failures.append(f"{prefix}: data has {duplicate_count} duplicate bar(s) by {duplicate_subset}.")
    if not df["timestamp"].is_monotonic_increasing:
        warnings.append(f"{prefix}: loaded data timestamps are not monotonic before sorting.")


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


def _print_human_result(result: dict) -> None:
    status = "PASS" if result["passed"] else "FAIL"
    print(f"Preflight {status}")
    print(f"Configs checked: {len(result['configs_checked'])}")
    print(f"Tests ran: {result['tests_ran']}")
    for warning in result["warnings"]:
        print(f"WARNING: {warning}")
    for failure in result["failures"]:
        print(f"FAIL: {failure}")


def _display_path(path: Path) -> Path:
    try:
        return path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        return path


if __name__ == "__main__":
    raise SystemExit(main())
